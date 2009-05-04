from amfast.remoting.channel import SecurityError

class Controller(object):
    def checkCredentials(self, user, password):
        """The checkCredentials method should always accept
        user and password arguments.

        The method should return True if the user
        authenticated, and raise a
        amfast.remoting.channel.SecurityError
        if the authentication failed.
        """

        if user != 'correct':
            raise SecurityError('Invalid credentials.')

        if password != 'correct':
            raise SecurityError('Invalid credentials.')

        return True

    def echo(self, val):
        return val

    def raiseException(self):
        raise Exception("Example Exception")
