def format_message(text, timestamp, username, age):
    """
    Formats message data into a dictionary for Jinja2.
    
    Doctests:
    >>> format_message("Hello", "2023-10-01", "Yumo", 19)
    {'text': 'Hello', 'timestamp': '2023-10-01', 'user': 'Alice', 'age': 25}
    
    >>> format_message("Hi", "2023-10-02", "Teddy", 5)
    {'text': 'Hi', 'timestamp': '2023-10-02', 'user': 'Bob', 'age': 30}
    """
    return {
        "text": text,
        "timestamp": timestamp,
        "user": username,
        "age": age
    }

if __name__ == "__main__":
    import doctest
    doctest.testmod()