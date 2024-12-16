import unittest
import sys
import re
import json
from io import StringIO

class TestJsonContent(unittest.TestCase):
    def __init__(self, methodName='runTest', output_file=None, test_file=None):
        super(TestJsonContent, self).__init__(methodName)
        self.output_file = output_file
        self.test_file = test_file

    def test_json_content(self):
        with open(self.output_file, 'r', encoding='utf-8') as f:
            output_json = json.load(f)
        with open(self.test_file, 'r', encoding='utf-8') as f:
            test_json = json.load(f)

        output_raw_content = output_json.get('raw_content', '')
        test_raw_content = test_json.get('raw_content', '')

        output_words = set(re.findall(r'\b\w+\b', output_raw_content))
        test_words = set(re.findall(r'\b\w+\b', test_raw_content))

        # Used to get the common words between the two sets
        common_words = output_words.intersection(test_words)

        if len(test_words) > 0:
            percentage = (len(output_words) / len(test_words)) * 100
        else:
            percentage = 0

        print(f"Percentage of words in the extracted JSON file that are also in the test JSON file: {percentage:.2f}%")
        # print(f"Common words: {common_words}") # Uncomment to see the common words
        print(f"Total words in test file: {len(test_words)}")
        print(f"Total words in output file: {len(output_words)}")

        # Log the assertion verification
        if percentage >= 80:
            print(f"Assertion passed: {percentage:.2f}% >= 80%")
        else:
            print(f"Assertion failed: {percentage:.2f}% < 80%")

        self.assertGreaterEqual(percentage, 80)

def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    output_file = sys.argv[1]
    test_file = sys.argv[2]
    suite.addTest(TestJsonContent('test_json_content', output_file=output_file, test_file=test_file))
    return suite

class DualOutput:
    def __init__(self, file_path):
        self.terminal = sys.stdout
        self.log = open(file_path, "w", encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python test_content.py path/to/output_file.json path/to/reference_file.json")
        sys.exit(1)

    # Redirect stdout to both console and file
    sys.stdout = DualOutput("test_results.txt")

    # Run the tests
    unittest.main(argv=sys.argv[:1])