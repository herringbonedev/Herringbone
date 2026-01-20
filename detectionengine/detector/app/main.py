from processor import process_one
import time

from modules.auth.service_auth import ensure_service_token, get_service_token


def main():
    print("[detector] started")

    # authenticate service on startup
    while True:
        if ensure_service_token():
            break
        print("[*] retrying service auth in 3s...")
        time.sleep(3)

    while True:
        try:
            token = get_service_token()

            processed = process_one(service_token=token)

            if not processed.get("status"):
                time.sleep(0.05)

        except Exception as e:
            print(f"[ERROR] detector loop failure: {e}")

            # refresh token on auth errors
            msg = str(e).lower()
            if "401" in msg or "unauthorized" in msg or "token" in msg:
                print("[*] refreshing service token...")
                ensure_service_token(force=True)

            time.sleep(0.1)


if __name__ == "__main__":
    main()
