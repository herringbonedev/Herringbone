from app.processor import process_one
import time


def main():
	print("[detector] started")

	while True:
		try:
			processed = process_one()
			if not processed.get("status"):
				time.sleep(0.05)
		except Exception as e:
			print(f"[ERROR] detector loop failure: {e}")
			time.sleep(0.1)


if __name__ == "__main__":
	main()
