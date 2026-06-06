import unittest

from artifactsmmo.service.helpers import BucketFiller


class TestBucketFiller(unittest.TestCase):
    def setUp(self):
        self.bucket_filler = BucketFiller(64)

    def test_no_items_to_equip(self):
        inventory_buckets_1 = self.bucket_filler.generate_buckets(130)
        self.assertEqual(
            inventory_buckets_1, [{'quantity': 64, 'full': True}, {'quantity': 64, 'full': True}, {'quantity': 2, 'full': False}]
        )
        self.assertEqual(self.bucket_filler.remaining_bucket_capacity, 64 - 2)

        inventory_buckets_2 = self.bucket_filler.generate_buckets(140)
        self.assertEqual(
            inventory_buckets_2, [{'quantity': 62, 'full': True}, {'quantity': 64, 'full': True}, {'quantity': 14, 'full': False}]
        )
        self.assertEqual(self.bucket_filler.remaining_bucket_capacity, 64 - 14)


if __name__ == '__main__':
    unittest.main()
