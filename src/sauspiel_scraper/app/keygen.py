from cryptography.fernet import Fernet


def generate_key():
    """
    Generates a new Fernet key and prints it to the console.
    This key should be stored in the FERNET_KEY environment variable.
    """
    key = Fernet.generate_key().decode()
    print(f"Generated Fernet Key: {key}")
    print("Add this to your .env file as: FERNET_KEY=" + key)


if __name__ == "__main__":
    generate_key()
