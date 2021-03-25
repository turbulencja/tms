class Error(Exception):
    """Base class for other exceptions"""
    pass


class EcIdsMismatchError(Error):
    """Raised when the EC ids mismatch"""
    def __init__(self, message='receiving data SQL database mishap'):
        self.message = message
        super().__init__(self.message)
