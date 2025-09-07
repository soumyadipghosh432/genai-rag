from typing import List
import re

def recursive_text_splitter(text: str, chunk_size: int, separators: List[str], debug: bool=False) -> List[str]:
    """
    Recursively splits a text into smaller chunks based on a list of separators.

    This function attempts to split the text using the first separator in the list.
    If the resulting chunks are still larger than the specified chunk_size, it
    recursively calls itself with the next separator in the list to further
    split those large chunks. This is useful for maintaining semantic integrity
    by splitting on larger units (like paragraphs) before resorting to smaller
    units (like sentences or words).

    Args:
        text (str): The input text to be split.
        chunk_size (int): The maximum size of each text chunk.
        separators (List[str]): A list of strings to split the text by, in order
                                of preference (e.g., ["\n\n", "\n", " ", ""]).

    Returns:
        List[str]: A list of text chunks, each approximately of size chunk_size.
    """
    # Base case: If no separators are left, split by character.
    if not separators:
        # If the text is larger than chunk_size, split it into chunks of that size.
        if len(text) > chunk_size:
            return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        else:
            return [text]

    # Get the first separator and the rest of the separators
    current_separator, *remaining_separators = separators

    # Split the text using the current separator. The pattern ensures the
    # separator is included in the output, which is then added back later.
    if current_separator:
        parts = re.split(f'({current_separator})', text)
    else:
        # If the separator is empty, treat each character as a part.
        parts = list(text)

    chunks = []
    current_chunk = ""

    for i, part in enumerate(parts):
        # Check if adding the next part would exceed the chunk size
        if len(current_chunk) + len(part) > chunk_size and current_chunk:
            # If so, add the current chunk to the list
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # Add the part to the current chunk
        current_chunk += part

        # If the current part is a separator, and we've already started a chunk
        if part in separators and current_chunk:
            # Add the chunk and start a new one
            chunks.append(current_chunk.strip())
            current_chunk = ""

    # Add the last remaining chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    # Now, check if any chunks are still too large and need further splitting
    final_chunks = []
    for chunk in chunks:
        if len(chunk) != 0:
            if len(chunk) > chunk_size:
                # If a chunk is too large, recursively split it with the next separator
                final_chunks.extend(recursive_text_splitter(chunk, chunk_size, remaining_separators))
            else:
                final_chunks.append(chunk)
    
    if debug:
        # Print the results
        print(f"Original text length: {len(text)} characters\n")
        print(f"Text split into {len(final_chunks)} chunks of max size {chunk_size}:\n")

        for i, chunk in enumerate(final_chunks):
            print(f"--- Chunk {i+1} (length: {len(chunk)}) ---")
            print(chunk)
            print("\n")

    return final_chunks



def customCharacterSplitter(text: str, chunk_size: int, chunk_overlap: int, debug=False) -> List[str]:
    """
    Splits a text into fixed-size chunks with a specified overlap between them.

    This function iterates through the input string, creating chunks of a
    defined size. Each new chunk starts at an offset determined by the
    `chunk_size` minus the `chunk_overlap`, ensuring that consecutive chunks
    share a portion of the text.

    Args:
        text (str):
            The input string to be split.
        chunk_size (int):
            The maximum length of each text chunk.
        chunk_overlap (int):
            The number of characters to overlap between adjacent chunks. This
            value must be less than `chunk_size`.
        debug (bool, optional):
            If `True`, prints each generated chunk to the console for
            debugging purposes. Defaults to `False`.

    Returns:
        List[str]:
            A list of strings, where each string is a chunk of the original text.
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - chunk_overlap
    
    if debug:
        for i, ch in enumerate(chunks, 1):
            print(f"Chunk {i}: {ch}")

    return chunks


# ---------------- USAGE EXAMPLE ----------------
if __name__ == "__main__":
    sample_text = f"""
        Ratan Tata is a revered Indian industrialist, investor, and philanthropist who served as the chairman of the Tata Group, a vast conglomerate, from 1991 to 2012. He is celebrated for transforming the group from a largely India-centric entity into a global powerhouse through a series of bold and strategic international acquisitions. His leadership is defined by a unique blend of visionary thinking, unwavering ethical integrity, and a deep-seated commitment to social responsibility.
        Early Life and Career
        Born on December 28, 1937, in Mumbai, Ratan Tata's early life was marked by a privileged yet grounded upbringing. After his parents separated, he was raised by his grandmother, Navajbai Tata, who instilled in him the core values of dignity and compassion. He received his education at prestigious institutions, including Cornell University, where he earned a bachelor's degree in architecture, and Harvard Business School. His architectural background, as he would later note, taught him to think with a blend of innovation and practicality—a skill he would apply to his business career. He joined the Tata Group in 1962, starting on the shop floor of Tata Steel, gaining a firsthand understanding of the company's operations before rising through the ranks.
        Visionary Leadership and Globalization
        When Ratan Tata took the helm of the Tata Group in 1991, India's economy was undergoing liberalization. He seized this opportunity to restructure and globalize the conglomerate. He orchestrated landmark acquisitions that put the Tata brand on the world map. These included Tata Tea's acquisition of the UK-based Tetley Group in 2000, Tata Steel's acquisition of the Anglo-Dutch Corus Group in 2007, and most notably, Tata Motors' acquisition of the iconic British luxury car brands Jaguar Land Rover from Ford in 2008. These moves cemented his reputation as a master strategist.
        He also championed ambitious, people-centric projects, such as the Tata Nano, which was conceived as the world's most affordable car. Though the project faced commercial hurdles, it remains a testament to his vision of providing accessible mobility to millions of Indian families.
        Philanthropy and Values
        Beyond his business acumen, Ratan Tata's legacy is deeply intertwined with his philanthropic efforts. He famously stated, "I don't believe in taking right decisions. I take decisions and then make them right." This philosophy underscores his commitment to accountability and doing what is right, even in the face of adversity. A significant portion of the Tata Group's profits—approximately 66% of the equity of Tata Sons—is channeled into charitable trusts, funding initiatives in healthcare, education, and rural development.
        Ratan Tata’s commitment to social good is a continuation of the Tata family's long-standing tradition. His support for causes like cancer care, education, and animal welfare through the Tata Trusts has had a profound impact on millions of lives. His leadership style is not just about profit; it's about purpose, embodying the belief that business success and social responsibility are not mutually exclusive but can work together for a lasting, positive impact on society.
    """
    chunk_size=800
    chunk_overlap=50

    ## Character Chunking
    print("---- Custom Splitter ----")
    customCharacterSplitter(
        text=sample_text, 
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap,
        debug=True
    )

    ## Recursive Text Splitting
    print("---- Recursive Text Splitter ----")
    separators_list = [
        "\n\n", 
        "\n"
        # " ",
        # ""
    ]
    split_chunks = recursive_text_splitter(
        text=sample_text, 
        chunk_size=chunk_size, 
        separators=separators_list,
        debug=True
    )
