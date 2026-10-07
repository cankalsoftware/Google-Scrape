import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tkinter as tk
import unittest
from scraper_gui import GoogleLeadScraperSuite, should_exclude_result, format_as_or_tokens, is_job_posting_url

class TestScraperFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = GoogleLeadScraperSuite()
        cls.app.withdraw() # Hide window during test

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_01_or_group_formatting(self):
        """Test + Quotes/OR formatting across different widgets."""
        # Tab 1: Org box
        self.app.org_box.set_real_value("Hilton Hotels, Marriott, Holiday Inn")
        self.app._format_as_or_group(self.app.org_box)
        val = self.app.org_box.get_real_value()
        self.assertEqual(val, '("Hilton Hotels" OR "Marriott" OR "Holiday Inn")')

        # Tab 2: Gen Industry box
        self.app.gen_ind_box.set_real_value("hotels, restaurants, tour operators")
        self.app._format_as_or_group(self.app.gen_ind_box)
        val = self.app.gen_ind_box.get_real_value()
        self.assertEqual(val, '("hotels" OR "restaurants" OR "tour operators")')

        # Tab 3: Civil Sector box
        self.app.civil_sec_box.set_real_value("Police, NHS Trust, Local Council")
        self.app._format_as_or_group(self.app.civil_sec_box)
        val = self.app.civil_sec_box.get_real_value()
        self.assertEqual(val, '("Police" OR "NHS Trust" OR "Local Council")')

    def test_02_exclusion_dropdown_chaining(self):
        """Test selecting items from exclusion dropdown merges tokens and resets combo index."""
        # Tab 1
        self.app._clear_targeted_exclusions()
        self.assertEqual(self.app.exclude_box.get_real_value(), "")

        # 1. Select Social Media
        self.app.targeted_exclude_combo.current(2) # Social Media
        self.app._on_targeted_exclude_selected()
        cur_t1 = self.app.exclude_box.get_real_value()
        self.assertIn("-facebook.com", cur_t1)
        self.assertIn("-instagram.com", cur_t1)
        self.assertEqual(self.app.targeted_exclude_combo.current(), 0) # Resets to 0

        # 2. Select OTA Portals
        self.app.targeted_exclude_combo.current(3) # OTA Portals
        self.app._on_targeted_exclude_selected()
        cur_t1 = self.app.exclude_box.get_real_value()
        self.assertIn("-facebook.com", cur_t1) # Still has social media
        self.assertIn("-tripadvisor.com", cur_t1) # Has OTA portals
        self.assertEqual(self.app.targeted_exclude_combo.current(), 0)

        # Tab 2: Test "Add ALL" option
        self.app._clear_gen_exclusions()
        self.app.gen_exclude_combo.current(1) # Add ALL
        self.app._on_gen_exclude_selected()
        cur_t2 = self.app.gen_ex_box.get_real_value()
        self.assertIn("-tripadvisor.com", cur_t2)
        self.assertIn("-jobs", cur_t2)
        self.assertIn("-facebook.com", cur_t2)
        self.assertIn("-yell.com", cur_t2)
        self.assertEqual(self.app.gen_exclude_combo.current(), 0)

        # Tab 3: Test Clear Exclude
        self.app._clear_civil_exclusions()
        self.assertEqual(self.app.civil_ex_box.get_real_value(), "")

    def test_03_clear_exclude_buttons(self):
        """Test Clear Exclude button on all 3 tabs."""
        # Tab 1
        self.app.exclude_box.set_real_value("-test -sample")
        self.app._clear_targeted_exclusions()
        self.assertEqual(self.app.exclude_box.get_real_value(), "")

        # Tab 2
        self.app.gen_ex_box.set_real_value("-test -sample")
        self.app._clear_gen_exclusions()
        self.assertEqual(self.app.gen_ex_box.get_real_value(), "")

        # Tab 3
        self.app.civil_ex_box.set_real_value("-test -sample")
        self.app._clear_civil_exclusions()
        self.assertEqual(self.app.civil_ex_box.get_real_value(), "")

    def test_04_domain_words_exclusion_filter(self):
        """Test should_exclude_result filtering domain words (uk.indeed.com, careers.*, etc.)."""
        exclusions = "-tripadvisor.com -booking.com -expedia.com -jobs -careers -recruiting -indeed.com -yell.com"
        
        # Should be excluded
        self.assertTrue(should_exclude_result("https://uk.indeed.com/viewjob?jk=abc", "Waiter Job", "Apply on Indeed", exclusions))
        self.assertTrue(should_exclude_result("https://careers.hilton.com/en/job/123", "Hilton Careers", "Jobs at Hilton", exclusions))
        self.assertTrue(should_exclude_result("https://www.marriott.com/careers/hotel-jobs", "Marriott Positions", "Careers", exclusions))
        self.assertTrue(should_exclude_result("https://www.tripadvisor.co.uk/Restaurant_Review", "Best Restaurants", "Reviews", exclusions))
        self.assertTrue(should_exclude_result("https://www.yell.com/biz/restaurant-123", "Restaurant on Yell", "Directory", exclusions))
        
        # Should be allowed (genuine operating business websites)
        self.assertFalse(should_exclude_result("https://www.didimhotel.com/rooms", "Didim Hotel", "Direct booking official site", exclusions))
        self.assertFalse(should_exclude_result("https://www.altinkumseafood.com/contact", "Altinkum Seafood", "Best fish restaurant in Didim", exclusions))

    def test_05_is_job_posting_subdomains(self):
        """Test is_job_posting_url detects subdomains like uk.indeed.com and careers.*."""
        self.assertTrue(is_job_posting_url("https://uk.indeed.com/jobs?q=chef"))
        self.assertTrue(is_job_posting_url("https://careers.google.com/jobs/results/"))
        self.assertTrue(is_job_posting_url("https://jobs.theguardian.com/job/123"))
        self.assertFalse(is_job_posting_url("https://www.hilton.com/en/hotels/didim/"))

if __name__ == '__main__':
    unittest.main()
