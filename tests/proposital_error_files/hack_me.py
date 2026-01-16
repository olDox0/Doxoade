# tests/proposital_error_files/hack_me.py
user_input = input("Enter something: ")
exec(user_input) # noqa (Intentional vulnerability for Hacking Suite testing)