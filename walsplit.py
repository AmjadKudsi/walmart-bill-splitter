import streamlit as st
import pdfplumber
import re
import pandas as pd
from streamlit_sortables import sort_items


def parse_receipt(pdf_file):
    '''
    Parse a PDF receipt and extract item lines with quantities and prices.
    Returns a DataFrame with columns: item, qty, total, unit_price.
    '''

    text = ''
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + '\n'
    # Extract order date
    date_match = re.search(r'([A-Z][a-z]{2,8} \d{1,2}, \d{4}) order', text)
    order_date = date_match.group(1) if date_match else "Date Not Found"

    # Extract items
    pattern = r'(.+?)\s+Qty\s+(\d+)\s+\$?(\d+\.\d{2})'
    rows = []

    for match in re.finditer(pattern, text):
        item, qty, total = match.groups()
        rows.append({'item': item.strip(), 'qty': int(qty), 'total': float(total)})

    df = pd.DataFrame(rows)

    # Safety check before accessing columns
    if df.empty or 'total' not in df.columns:
        return pd.DataFrame(), order_date

    df['unit_price'] = df['total'] / df['qty']
    return df, order_date



def build_summary(df, assignments, people, order_date):
    """
    Given the parsed items, assignment mapping, and list of people,
    compute per-person costs and generate summary text.
    """
    assign_df = df.copy()
    # for each person, add qty and cost columns
    for person in people:
        assign_df[person] = assign_df.index.map(lambda i: assignments[i].get(person, 0))
        assign_df[f"{person}_cost"] = assign_df[person] * assign_df["unit_price"]

    # header with date
    output = f"{order_date}:\n\n"

    # per-person breakdown
    for person in people:
        total_cost = assign_df[f"{person}_cost"].sum()
        output += f"{person}: ${total_cost:.2f}\n"
        person_rows = assign_df[assign_df[person] > 0]
        for _, row in person_rows.iterrows():
            qty  = int(row[person])
            cost = row[f"{person}_cost"]
            output += f"{qty}× {row['item']} – ${cost:.2f}\n"
        output += "\n"

    # 4) new grand total = sum of all people’s totals (unassigned is not in people)
    total_allocated = sum(assign_df[f"{p}_cost"].sum() for p in people)
    output += f"Grand Total = ${total_allocated:.2f}\n"

    return output

def add_member():
    """Add the typed-in name to session_state.members, then clear the input."""
    name = st.session_state.new_member.strip()
    if name and name not in st.session_state.members:
        st.session_state.members.append(name)
    st.session_state.new_member = ""  # clear the box

def main():
    st.set_page_config(layout="wide")
    st.title("Walmart Bill Splitter")

    # --- Sidebar: manage members ---
    if "members" not in st.session_state:
        st.session_state.members = []

    # Initialize storage for extra items
    if "extra_items" not in st.session_state:
        st.session_state.extra_items = []


    with st.sidebar.expander("Members"):
        # Pressing Enter here calls add_member()
        st.text_input("Member name", key="new_member", on_change=add_member)
        # Or click button
        if st.button("Add member"):
            add_member()

        st.markdown("**Current members:**")
        if st.session_state.members:
            for m in st.session_state.members:
                st.markdown(f"- {m}")
        else:
            st.markdown("_None_")

    # Receipt upload
    uploaded_file = st.file_uploader('Upload Receipt PDF', type='pdf')
    if not uploaded_file:
        return

    with st.spinner('Parsing receipt...'):
        df, order_date = parse_receipt(uploaded_file)
    if df.empty:
        st.error('No items found. Please check receipt format.')
        return

    people = st.session_state.members
    if not people:
        st.warning('Please add at least one member above!')
        return

    with st.expander("Add Extra Item (e.g., Tax, Tips, Fees)"):
        new_item_name = st.text_input("Item name", key="custom_item_name")
        new_item_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="custom_item_qty")
        new_item_total = st.number_input("Total cost ($)", min_value=0.01, format="%.2f", key="custom_item_total")

        if st.button("Add Extra Item"):
            new_row = {
                'item': new_item_name,
                'qty': int(new_item_qty),
                'total': float(new_item_total),
                'unit_price': float(new_item_total) / int(new_item_qty)
            }
            st.session_state.extra_items.append(new_row)
            st.success(f"Added: {new_item_name} (${new_item_total:.2f})")
            st.rerun()

    # Append manually added items to the parsed receipt
    if st.session_state.extra_items:
        df = pd.concat([df, pd.DataFrame(st.session_state.extra_items)], ignore_index=True)

    st.subheader('Parsed Items')
    st.dataframe(df)
    #st.write("Custom Items in Memory:", st.session_state.extra_items)

    # Prepare unit cards
    unit_cards = []
    for idx, row in df.iterrows():
        for i in range(int(row['qty'])):
            unit_cards.append(f"{idx}_{i}: {row['item']}")


    # Build Kanban containers: members on the left, Unassigned on the right
    containers = []
    for person in people:
        containers.append({'header': person, 'items': []})
    containers.append({'header': 'Unassigned', 'items': unit_cards.copy()})

    st.subheader('Assign Items via Drag-and-Drop Kanban')
    assigned_containers = sort_items(
        containers,
        multi_containers=True,
        key='kanban_' + '_'.join(people) + f"_{len(df)}"
    )

    #st.write("Cards to display:", unit_cards)



    # Tally assignments
    assignments = {idx: {person: 0 for person in people} for idx in df.index}
    for container in assigned_containers:
        person = container['header']
        if person == 'Unassigned':
            continue
        for card in container['items']:
            idx_str = card.split(':')[0].split('_')[0]
            idx = int(idx_str)
            assignments[idx][person] += 1

    if st.button('Compute Summary'):
        summary = build_summary(df, assignments, people, order_date)
        st.subheader('Summary')
        st.text(summary)
        st.download_button(
            'Download',
            summary,
            file_name='receipt_summary.txt',
            mime='text/plain'
        )

if __name__ == '__main__':
    main()