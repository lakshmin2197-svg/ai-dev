import unittest

from evaluate import score_answer


class TestScoreAnswerValue(unittest.TestCase):
    def test_exact_number_match(self):
        self.assertTrue(score_answer("Based on the data, the result is 50.", "50", "value"))

    def test_comma_formatted_number_matches_plain_expected(self):
        self.assertTrue(
            score_answer("The total is 37,888,285 dollars.", "37888285", "value")
        )

    def test_mismatched_number_fails(self):
        self.assertFalse(score_answer("Based on the data, the result is 51.", "50", "value"))

    def test_case_insensitive_text_match(self):
        self.assertTrue(score_answer("The sector is Energy.", "energy", "value"))

    def test_empty_expected_fails_closed(self):
        self.assertFalse(score_answer("anything at all", "", "value"))

    def test_non_string_answer_fails(self):
        self.assertFalse(score_answer(None, "50", "value"))


class TestScoreAnswerRefusal(unittest.TestCase):
    def test_default_refusal_string_is_detected(self):
        self.assertTrue(
            score_answer("I don't have that information in the dataset.", "", "refusal")
        )

    def test_alternate_refusal_phrasing_is_detected(self):
        self.assertTrue(score_answer("Sorry, I cannot answer that question.", "", "refusal"))

    def test_fabricated_number_is_not_mistaken_for_a_refusal(self):
        self.assertFalse(score_answer("Based on the data, the result is 42.", "", "refusal"))


if __name__ == "__main__":
    unittest.main()
