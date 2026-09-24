import unittest

from scripts.update_press_highlights import parse_feed


class FeedParserTest(unittest.TestCase):
    def test_parses_and_cleans_rss_item(self):
        payload = b"""<rss><channel><item>
          <title>Una &amp;amp; noticia - Reuters</title>
          <link>https://example.com/story</link><pubDate>Wed, 23 Sep 2026 10:00:00 GMT</pubDate>
          <source>Reuters</source></item></channel></rss>"""
        self.assertEqual(parse_feed(payload, "Reuters"), [{
            "titulo": "Una & noticia", "fuente": "Reuters", "fecha": "2026-09-23",
            "url": "https://example.com/story",
        }])


if __name__ == "__main__":
    unittest.main()
