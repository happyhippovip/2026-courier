def reserve_genesis_block(client, company_name, logo_url):
    print(f"Reserving POW-001 Genesis Block for {company_name}...")
    response = client.post("/pow001/reserve", {"company_name": company_name, "logo_url": logo_url})
    if response.get("status") == "success":
        print(f"Success! Block {response['block_id']} reserved.")
        print(f"Invoice ID: {response['invoice']['invoice_id']}")
        print(f"Send {response['invoice']['amount_btc']} BTC to {response['invoice']['btc_address']}")
    else:
        print(f"Error: {response.get('message')}")
