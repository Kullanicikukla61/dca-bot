import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime

class DCABot:
    def __init__(self):
        self.config_file = "dca_strategies.json"
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump({}, f)

    def calculate_strategy(self, base_price, base_order, safety_orders, price_step, volume_scale, step_scale, tp_pct):
        """Generates the DCA grid based on parameters."""
        strategy = []
        cumulative_spent = base_order
        cumulative_volume = base_order / base_price
        last_price = base_price
        last_order_size = base_order
        current_deviation = price_step

        # Step 0: Base Order
        strategy.append({
            "Step": "Base",
            "Buy Price ($)": round(base_price, 2),
            "Order Size ($)": round(base_order, 2),
            "Total Investment ($)": round(cumulative_spent, 2),
            "Avg Price ($)": round(base_price, 2),
            "TP Target ($)": round(base_price * (1 + tp_pct / 100), 2),
            "Drop %": 0.0
        })

        # Calculate Safety Orders
        for i in range(1, safety_orders + 1):
            buy_price = last_price * (1 - current_deviation / 100)
            order_size = last_order_size * volume_scale
            
            cumulative_spent += order_size
            cumulative_volume += order_size / buy_price
            avg_price = cumulative_spent / cumulative_volume
            
            strategy.append({
                "Step": f"SO #{i}",
                "Buy Price ($)": round(buy_price, 2),
                "Order Size ($)": round(order_size, 2),
                "Total Investment ($)": round(cumulative_spent, 2),
                "Avg Price ($)": round(avg_price, 2),
                "TP Target ($)": round(avg_price * (1 + tp_pct / 100), 2),
                "Drop %": round(((base_price - buy_price) / base_price) * 100, 2)
            })

            last_price = buy_price
            last_order_size = order_size
            current_deviation *= step_scale

        return strategy

    def save_strategy(self, name, params, grid):
        with open(self.config_file, 'r') as f:
            data = json.load(f)
        
        data[name] = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "parameters": params,
            "grid": grid
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)

    def delete_strategy(self, name):
        with open(self.config_file, 'r') as f:
            data = json.load(f)
        if name in data:
            del data[name]
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        return False

    def load_all_strategies(self):
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

# --- Streamlit UI ---

def main():
    st.set_page_config(page_title="DCA Strategy Bot", layout="wide")
    bot = DCABot()

    st.title("🤖 DCA Strategy Planner")
    st.markdown("Calculate your buy-the-dip points and manage your take-profit targets.")

    # Initialize Session State for parameters if not exists
    if 'params' not in st.session_state:
        st.session_state.params = {
            "base_price": 50000.0, "base_order": 100.0, "safety_orders": 5,
            "price_step": 2.0, "volume_scale": 1.5, "step_scale": 1.1, "tp_pct": 1.5
        }

    # Sidebar for Inputs
    st.sidebar.header("Parameters")
    
    # We use session state to populate values so they can be changed by loading a strategy
    base_price = st.sidebar.number_input("Initial Price ($)", value=st.session_state.params["base_price"], step=100.0)
    base_order = st.sidebar.number_input("Base Order Size ($)", value=st.session_state.params["base_order"], step=10.0)
    safety_orders = st.sidebar.number_input("Number of Safety Orders", value=st.session_state.params["safety_orders"], min_value=0, max_value=20)
    price_step = st.sidebar.number_input("Price Deviation (%)", value=st.session_state.params["price_step"], step=0.1)
    volume_scale = st.sidebar.number_input("Volume Scale (Multiplier)", value=st.session_state.params["volume_scale"], step=0.1)
    step_scale = st.sidebar.number_input("Step Scale (Multiplier)", value=st.session_state.params["step_scale"], step=0.1)
    tp_pct = st.sidebar.number_input("Take Profit (%)", value=st.session_state.params["tp_pct"], step=0.1)
    
    save_name = st.sidebar.text_input("Strategy Name (to save)", value="My Strategy")
    
    if st.sidebar.button("Save Current Strategy"):
        current_params = {
            "base_price": base_price, "base_order": base_order, "safety_orders": safety_orders,
            "price_step": price_step, "volume_scale": volume_scale, "step_scale": step_scale, "tp_pct": tp_pct
        }
        grid = bot.calculate_strategy(**current_params)
        bot.save_strategy(save_name, current_params, grid)
        st.sidebar.success(f"Saved '{save_name}'!")
        st.rerun()

    # Current Logic - Always calculate based on current sidebar inputs
    active_params = {
        "base_price": base_price, "base_order": base_order, "safety_orders": safety_orders,
        "price_step": price_step, "volume_scale": volume_scale, "step_scale": step_scale, "tp_pct": tp_pct
    }
    current_grid = bot.calculate_strategy(**active_params)
    df = pd.DataFrame(current_grid)

    # Main Display
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Active Strategy Grid")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Summary Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Investment", f"${df['Total Investment ($)'].iloc[-1]:,.2f}")
        m2.metric("Max Price Drop Covered", f"-{df['Drop %'].iloc[-1]}%")
        m3.metric("Final TP Target", f"${df['TP Target ($)'].iloc[-1]:,.2f}")

    with col2:
        st.subheader("Strategy Management")
        saved = bot.load_all_strategies()
        
        if not saved:
            st.info("No saved strategies yet.")
        else:
            selected_strategy_name = st.selectbox("Select Saved Strategy", options=list(saved.keys()))
            
            if selected_strategy_name:
                strat = saved[selected_strategy_name]
                st.write(f"**Timestamp:** {strat['timestamp']}")
                
                c1, c2 = st.columns(2)
                
                # LOAD BUTTON: This updates the session state and reruns
                if c1.button("📂 Load Parameters", use_container_width=True):
                    st.session_state.params = strat['parameters']
                    st.rerun()
                
                if c2.button("🗑️ Delete", type="secondary", use_container_width=True):
                    if bot.delete_strategy(selected_strategy_name):
                        st.rerun()

                # Quick Trigger Tool (based on ACTIVE grid)
                st.divider()
                st.write("🎯 **Quick Trigger Price Lookup**")
                triggered_step = st.selectbox("Which order just hit?", options=df['Step'].tolist())
                
                trigger_row = df[df['Step'] == triggered_step].iloc[0]
                st.success(f"**Target Exit Price:** ${trigger_row['TP Target ($)']:,.2f}")
                st.info(f"Break-Even: ${trigger_row['Avg Price ($)']:,.2f}")

if __name__ == "__main__":
    main()