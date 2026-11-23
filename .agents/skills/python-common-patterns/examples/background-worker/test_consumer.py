import sqlite3
import unittest

from consumer import Message, consume, init_db


class ConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        init_db(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_duplicate_delivery_only_one_effect(self) -> None:
        message = Message("e-1", "order-1")
        self.assertTrue(consume(self.conn, message))
        self.assertFalse(consume(self.conn, message))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM inbox").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM processed_orders").fetchone()[0], 1)

    def test_failed_business_write_rolls_back_inbox(self) -> None:
        self.assertTrue(consume(self.conn, Message("e-1", "order-1")))
        with self.assertRaises(sqlite3.IntegrityError):
            consume(self.conn, Message("e-2", "order-1"))  # order_id unique collision
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM inbox").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM processed_orders").fetchone()[0], 1)

    def test_invalid_message_rejected_without_write(self) -> None:
        with self.assertRaises(ValueError):
            consume(self.conn, Message("", "order-1"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM inbox").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
