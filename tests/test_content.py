"""Checks for date boundaries, unsafe links, and resilient publication refreshes."""
import copy
import importlib.util
import io
import json
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import site_data
import sync_publications

class DataTests(unittest.TestCase):
    def test_deadline_includes_final_day(self):
        row = {'status':'open', 'deadline':'2026-09-28'}
        self.assertEqual(site_data.job_status(row, date(2026,9,28)), 'open')
        self.assertEqual(site_data.job_status(row, date(2026,9,29)), 'closed')

    def test_until_filled_and_explicit_status(self):
        self.assertEqual(site_data.job_status({'status':'open','deadline':''}), 'open')
        self.assertEqual(site_data.job_status({'status':'closed','deadline':'2099-01-01'}), 'closed')
        self.assertEqual(site_data.job_status({'status':'draft'}), 'draft')

    def test_doi_versions_and_case(self):
        self.assertEqual(site_data.normalise_doi('https://doi.org/10.32942/X24P8S'), '10.32942/x24p8s')
        self.assertEqual(site_data.normalise_doi('10.1101/2025.01.26.634944v1'), '10.1101/2025.01.26.634944')
        self.assertEqual(site_data.normalise_doi('10.5281/zenodo.123.v1'), '10.5281/zenodo.123.v1')

    def test_unsafe_links_rejected(self):
        for url in ['javascript:alert(1)', '//example.com', '../private.txt', 'file:///C:/private.txt']:
            with self.assertRaises(ValueError): site_data.safe_url(url)
        self.assertEqual(site_data.safe_url('downloads/job.pdf'), 'downloads/job.pdf')

    def test_job_has_usable_source_and_link(self):
        row = {'id':'test', 'title':'Test announcement', 'type':'PhD', 'institution':'Test institution', 'source':'Shared opportunity', 'summary':'Test description', 'pdf':'downloads/example.pdf', 'status':'open'}
        site_data.validate_jobs([row])
        with self.assertRaises(ValueError): site_data.validate_jobs([row, row])
        with self.assertRaises(ValueError): site_data.validate_jobs([{**row, 'pdf':''}])

    def test_failed_refresh_preserves_saved_record(self):
        doi = '10.1000/test'
        original = {'csl':{'title':'Saved title','author':[{'family':'Petitjean','given':'Quentin'}]}, 'fetched_at':'2026-01-01'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'data').mkdir()
            (root/'data/publications.csv').write_text('Title;DOI\nSaved title;10.1000/test\n', encoding='utf-8')
            site_data.write_json(root/'data/publications-cache.json', {'entries':{doi:original}, 'discovered':{}, 'last_success':'2026-01-01'})
            args = types.SimpleNamespace(no_discovery=True, scholar_bib=None, only_missing=False)
            with patch.object(sync_publications, 'ROOT', root), patch.object(sync_publications, 'fetch_json', side_effect=OSError('offline')), patch.object(sync_publications.time, 'sleep'), redirect_stdout(io.StringIO()):
                sync_publications.sync(args)
            after = site_data.read_json(root/'data/publications-cache.json')
            self.assertEqual(after['entries'][doi], original)
            self.assertEqual(after['last_success'], '2026-01-01')
            self.assertEqual(len(site_data.read_json(root/'data/sync-report.json')['failures']), 1)

if __name__ == '__main__': unittest.main()

