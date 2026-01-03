from processor import process_one
import time


def main():
	while True:
		try:
			processed = process_one()
			if not processed.get("status"):
				time.sleep(0.05)
		except Exception as e:
			print(f"[✗] Detector failed {str(e)}")
			time.sleep(0.05)


if __name__ == "__main__":
	main()
