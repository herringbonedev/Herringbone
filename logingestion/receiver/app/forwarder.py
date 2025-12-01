import requests

def forward_data(route, data, source_addr):
    """
    Forwards log to remote receiver route
    """

    payload = {
        "remote_from": {"source_addr": source_addr},
        "data": data
    }

    try:
        response = requests.get(route, json=payload)
        print(f"[*] Forwarded log to {route}")
        print(f"[*] Response: {str(response.content)}")
        return True

    except Exception as e:
        print(f"[*] Something went wrong with forwarding to {route}\n{str(e)}")
        return False