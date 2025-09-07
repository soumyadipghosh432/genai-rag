import tiktoken

def count_tokens(text: str, model_name: str = "cl100k_base", debug=False) -> int:
    """
    Calculates the number of tokens in a given text string using tiktoken.
    Args:
        text (str): The input text to tokenize.
        model_name (str): The encoding name or model name to use.
                          Defaults to "cl100k_base" which is used by models
                          like GPT-4, GPT-3.5-Turbo, and more.
    Returns:
        int: The number of tokens in the text.
    """
    encoding = tiktoken.get_encoding(model_name)
    token_integers = encoding.encode(text)

    if debug:
        print(f"Token integers: {token_integers}")
        decoded_tokens = [encoding.decode_single_token_bytes(token).decode('utf-8') for token in token_integers]
        print(f"Decoded tokens: {decoded_tokens}")    
        print(f"Token count: {len(token_integers)}")

    return len(token_integers)


if __name__ == "__main__":
    sample_text = "Hello, world! This is a test string to count tokens."
    print(f"Token Count : {count_tokens(text=sample_text, debug=False)}")