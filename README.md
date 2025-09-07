# genai-rag

Learning code repo for different RAG related strategies and code snippets in GenAI

## Chunking Strategies

This repository implements two main text chunking strategies in [`chunking.py`](chunking.py):

- **Recursive Text Splitter**:  
  The [`recursive_text_splitter`](chunking.py) function splits text into chunks based on a list of separators (e.g., paragraphs, newlines), recursively splitting large chunks with finer separators.  
  Useful for maintaining semantic integrity.

- **Custom Character Splitter**:  
  The [`customCharacterSplitter`](chunking.py) function splits text into fixed-size chunks with a specified overlap, ensuring consecutive chunks share a portion of the text.

## Usage Example

Run the script directly to see both chunking methods in action:

```sh
python chunking.py
```

You can modify the sample text, chunk size, and overlap in the `__main__` section of [`chunking.py`](chunking.py).

## Functions

- [`recursive_text_splitter`](chunking.py):  
  Recursively splits text using a list of separators and a maximum chunk size.

- [`customCharacterSplitter`](chunking.py):  
  Splits text into overlapping fixed-size chunks.

See [`chunking.py`](chunking.py) for full implementation and example
