import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models as django_models

from easy_thumbnails.fields import ThumbnailerField
from easy_thumbnails.management.commands.thumbnail import _collect_fields, _matches
from tests import utils as test
from tests.models import TestModel


class CollectFieldsTest(test.BaseTest):
    def _pairs(self, **kwargs):
        return list(_collect_fields(**kwargs))

    def _labels(self, **kwargs):
        return {(m._meta.label, f.name) for m, f in self._pairs(**kwargs)}

    def test_default_finds_thumbnailer_image_fields(self):
        self.assertIn(('easy_thumbnails_tests.TestModel', 'picture'), self._labels())

    def test_default_excludes_plain_file_fields(self):
        # Profile.logo is a plain FileField — not a ThumbnailerImageField
        self.assertNotIn(('easy_thumbnails_tests.Profile', 'logo'), self._labels())

    def test_default_excludes_thumbnailer_non_image_fields(self):
        # ThumbnailerField is not a ThumbnailerImageField subclass
        self.assertNotIn(('easy_thumbnails_tests.TestModel', 'avatar'), self._labels())
        self.assertNotIn(('easy_thumbnails_tests.Profile', 'avatar'), self._labels())

    def test_custom_field_class_file_field(self):
        # Passing models.FileField widens the search to all file-based fields
        labels = self._labels(field_class=django_models.FileField)
        self.assertIn(('easy_thumbnails_tests.Profile', 'logo'), labels)
        self.assertIn(('easy_thumbnails_tests.TestModel', 'picture'), labels)

    def test_custom_field_class_thumbnailer_field(self):
        # ThumbnailerImageField is also a ThumbnailerField subclass
        labels = self._labels(field_class=ThumbnailerField)
        self.assertIn(('easy_thumbnails_tests.Profile', 'avatar'), labels)
        self.assertIn(('easy_thumbnails_tests.TestModel', 'avatar'), labels)
        self.assertIn(('easy_thumbnails_tests.TestModel', 'picture'), labels)

    def test_fields_sorted_within_each_model(self):
        from itertools import groupby

        pairs = self._pairs(field_class=django_models.FileField)
        for _, group in groupby(
            pairs, key=lambda p: (p[0]._meta.app_label, p[0]._meta.model_name)
        ):
            names = [f.name for _, f in group]
            self.assertEqual(names, sorted(names))

    def test_yields_model_field_tuples(self):
        for model, field in self._pairs(field_class=django_models.FileField):
            self.assertTrue(hasattr(model, '_meta'))
            self.assertTrue(hasattr(field, 'name'))


class MatchesTest(test.BaseTest):
    def setUp(self):
        super().setUp()
        # TestModel.picture is the only ThumbnailerImageField in test models
        self._model, self._field = next(
            (m, f)
            for m, f in _collect_fields()
            if m._meta.label == 'easy_thumbnails_tests.TestModel' and f.name == 'picture'
        )

    def test_empty_specs_always_matches(self):
        self.assertTrue(_matches(self._model, self._field, []))

    def test_matches_by_app(self):
        self.assertTrue(_matches(self._model, self._field, ['easy_thumbnails_tests']))

    def test_no_match_wrong_app(self):
        self.assertFalse(_matches(self._model, self._field, ['auth']))

    def test_matches_by_app_model(self):
        self.assertTrue(
            _matches(self._model, self._field, ['easy_thumbnails_tests.testmodel'])
        )

    def test_no_match_wrong_model(self):
        self.assertFalse(
            _matches(self._model, self._field, ['easy_thumbnails_tests.profile'])
        )

    def test_matches_by_app_model_field(self):
        self.assertTrue(
            _matches(
                self._model, self._field, ['easy_thumbnails_tests.testmodel.picture']
            )
        )

    def test_no_match_wrong_field(self):
        self.assertFalse(
            _matches(self._model, self._field, ['easy_thumbnails_tests.testmodel.avatar'])
        )

    def test_wildcard_app(self):
        self.assertTrue(_matches(self._model, self._field, ['easy_thumbnails*']))

    def test_wildcard_model(self):
        self.assertTrue(
            _matches(self._model, self._field, ['easy_thumbnails_tests.test*'])
        )

    def test_wildcard_field(self):
        self.assertTrue(
            _matches(self._model, self._field, ['easy_thumbnails_tests.testmodel.*'])
        )

    def test_any_matching_spec_returns_true(self):
        self.assertTrue(
            _matches(self._model, self._field, ['auth', 'easy_thumbnails_tests'])
        )


class ThumbnailSourceFilesCommandTest(test.BaseTest):
    def _call(self, **kwargs):
        stdout = io.StringIO()
        stderr = io.StringIO()
        call_command('thumbnail', 'source_files', stdout=stdout, stderr=stderr, **kwargs)
        return stdout.getvalue(), stderr.getvalue()

    def test_list_mode_empty_db_no_output(self):
        stdout, stderr = self._call()
        self.assertEqual(stdout, '')
        self.assertIn('total', stderr)

    def test_list_mode_outputs_file_paths(self):
        TestModel.objects.create(avatar='avatars/a.jpg', picture='pictures/p.jpg')
        stdout, _ = self._call()
        lines = stdout.splitlines()
        self.assertIn('pictures/p.jpg', lines)

    def test_list_mode_skips_empty_paths(self):
        TestModel.objects.create(avatar='', picture='')
        stdout, _ = self._call()
        self.assertEqual(stdout, '')

    def test_summary_mode_shows_field_label(self):
        stdout, _ = self._call(summary=True)
        self.assertIn('easy_thumbnails_tests.TestModel.picture', stdout)

    def test_stderr_reports_field_and_model_counts(self):
        _, stderr = self._call()
        self.assertIn('fields', stderr)
        self.assertIn('models', stderr)

    def test_include_limits_to_matching_model(self):
        stdout, _ = self._call(include=['easy_thumbnails_tests.testmodel'], summary=True)
        self.assertIn('TestModel', stdout)

    def test_include_no_match_returns_empty(self):
        stdout, _ = self._call(include=['auth'], summary=True)
        self.assertEqual(stdout, '')

    def test_exclude_hides_matching_model(self):
        # TestModel excluded and no other ThumbnailerImageField models, output is empty
        stdout, _ = self._call(exclude=['easy_thumbnails_tests.testmodel'], summary=True)
        self.assertNotIn('TestModel', stdout)

    def test_include_and_exclude_combined(self):
        stdout, _ = self._call(
            include=['easy_thumbnails_tests'],
            exclude=['easy_thumbnails_tests.testmodel'],
            summary=True,
        )
        self.assertNotIn('TestModel', stdout)

    def test_invalid_spec_too_many_parts(self):
        with self.assertRaises(CommandError):
            self._call(include=['too.many.parts.here'])

    def test_invalid_spec_in_exclude(self):
        with self.assertRaises(CommandError):
            self._call(exclude=['a.b.c.d'])
