class ResultVerifier:
    def __init__(self, expected_output: str = ""):
        self.expected = expected_output.strip()

    def check(self, stdout: str, stderr: str) -> bool:
        if self.expected:
            return self.expected in stdout.strip()
        return stderr.strip() == "" and "Traceback" not in stdout