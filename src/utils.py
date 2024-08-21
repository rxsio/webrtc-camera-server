import logging


def create_logger(name: str) -> logging.Logger:
    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s]: %(message)s")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(f"{name}.log")
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    return logger