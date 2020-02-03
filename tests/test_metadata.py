from unittest import TestCase
from unittest.mock import MagicMock, Mock, call, patch

import graphviz
import pandas as pd
import pytest

from sdv.metadata import Metadata, MetadataError, _load_csv, _parse_dtypes, _read_csv_dtypes


def test__read_csv_dtypes():
    """Test read csv data types"""
    # Run
    table_meta = {
        'fields': {
            'a_field': {
                'type': 'categorical'
            },
            'b_field': {
                'type': 'boolean'
            },
            'c_field': {
                'type': 'datetime',
            },
            'd_field': {
                'type': 'id',
                'subtype': 'string'
            },
            'e_field': {
                'type': 'id',
                'subtype': 'integer'
            }
        }
    }
    result = _read_csv_dtypes(table_meta)

    # Asserts
    assert result == {'a_field': str, 'd_field': str}


def test__parse_dtypes():
    """Test parse data types"""
    # Run
    data = pd.DataFrame({
        'a_field': ['1996-10-17', '1965-05-23'],
        'b_field': ['7', '14'],
        'c_field': ['1', '2'],
        'd_field': ['other', 'data']
    })
    table_meta = {
        'fields': {
            'a_field': {
                'type': 'datetime',
                'format': '%Y-%m-%d'
            },
            'b_field': {
                'type': 'numerical',
                'subtype': 'integer'
            },
            'c_field': {
                'type': 'id',
                'subtype': 'integer'
            },
            'd_field': {
                'type': 'other'
            }
        }
    }
    result = _parse_dtypes(data, table_meta)

    # Asserts
    expected = pd.DataFrame({
        'a_field': pd.to_datetime(['1996-10-17', '1965-05-23'], format='%Y-%m-%d'),
        'b_field': [7, 14],
        'c_field': [1, 2],
        'd_field': ['other', 'data']
    })
    pd.testing.assert_frame_equal(result, expected)


@patch('sdv.metadata._parse_dtypes')
@patch('sdv.metadata.pd.read_csv')
@patch('sdv.metadata._read_csv_dtypes')
def test__load_csv(rcdtypes_mock, read_csv_mock, pdtypes_mock):
    # Run
    table_meta = {
        'path': 'filename.csv',
        'other': 'stuff'
    }
    result = _load_csv('a/path', table_meta)

    # Asserts
    assert result == pdtypes_mock.return_value
    rcdtypes_mock.assert_called_once_with(table_meta)
    dtypes = rcdtypes_mock.return_value
    read_csv_mock.assert_called_once_with('a/path/filename.csv', dtype=dtypes)
    pdtypes_mock.assert_called_once_with(read_csv_mock.return_value, table_meta)


class TestMetadata(TestCase):
    """Test Metadata class."""

    def test__analyze_relationships(self):
        """Test get relationships"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        _metadata = {
            'tables': {
                'test': {
                    'use': True,
                    'name': 'test',
                    'fields': {
                        'test_field': {
                            'ref': {'table': 'table_ref', 'field': 'field_ref'},
                            'name': 'test_field'
                        }
                    }
                },
                'test_not_use': {
                    'use': False,
                    'name': 'test_not_use',
                    'fields': {
                        'test_field_not_use': {
                            'ref': {'table': 'table_ref', 'field': 'field_ref'},
                            'name': 'test_field_not_use'
                        }
                    }
                }
            }
        }
        metadata._metadata = _metadata

        # Run
        Metadata._analyze_relationships(metadata)

        # Asserts
        assert metadata._child_map == {'table_ref': {'test'}}
        assert metadata._parent_map == {'test': {'table_ref'}}

    def test__dict_metadata_list(self):
        """Test dict_metadata"""
        # Run
        metadata = {
            'tables': [
                {
                    'name': 'test',
                    'fields': [
                        {
                            'ref': {
                                'table': 'table_ref',
                                'field': 'field_ref'
                            },
                            'name': 'test_field'
                        }
                    ]
                },
                {
                    'name': 'other',
                    'use': False,
                }
            ]
        }
        result = Metadata._dict_metadata(metadata)

        # Asserts
        expected = {
            'tables': {
                'test': {
                    'fields': {
                        'test_field': {
                            'ref': {
                                'table': 'table_ref',
                                'field': 'field_ref'
                            }
                        }
                    }
                }
            }
        }
        assert result == expected

    def test__dict_metadata_dict(self):
        """Test dict_metadata"""
        # Run
        metadata = {
            'tables': {
                'test': {
                    'fields': {
                        'test_field': {
                            'ref': {
                                'table': 'table_ref',
                                'field': 'field_ref'
                            }
                        }
                    }
                },
                'other': {
                    'use': False,
                }
            }
        }
        result = Metadata._dict_metadata(metadata)

        # Asserts
        expected = {
            'tables': {
                'test': {
                    'fields': {
                        'test_field': {
                            'ref': {
                                'table': 'table_ref',
                                'field': 'field_ref'
                            }
                        }
                    }
                }
            }
        }
        assert result == expected

    def test__validate_parents_no_error(self):
        """Test that any error is raised with a supported structure"""
        # Setup
        mock = MagicMock(spec_set=Metadata)
        mock.get_parents.return_value = []

        # Run
        Metadata._validate_parents(mock, 'demo')

        # Asserts
        mock.get_parents.assert_called_once_with('demo')

    def test__validate_parents_raise_error(self):
        """Test that a ValueError is raised because the bad structure"""
        # Setup
        mock = MagicMock(spec_set=Metadata)
        mock.get_parents.return_value = ['foo', 'bar']

        # Run
        with pytest.raises(MetadataError):
            Metadata._validate_parents(mock, 'demo')

    @patch('sdv.metadata.Metadata._analyze_relationships')
    @patch('sdv.metadata.Metadata._dict_metadata')
    def test___init__default_metadata_dict(self, mock_meta, mock_relationships):
        """Test create Metadata instance default with a dict"""
        # Run
        metadata = Metadata({'some': 'meta'})

        # Asserts
        mock_meta.assert_called_once_with({'some': 'meta'})
        mock_relationships.assert_called_once_with()
        assert metadata.root_path == '.'
        assert metadata._hyper_transformers == dict()

    def test_get_children(self):
        """Test get children"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata._child_map = {
            'test': 'child_table'
        }

        # Run
        result = Metadata.get_children(metadata, 'test')

        # Asserts
        assert result == 'child_table'

    def test_get_parents(self):
        """Test get parents"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata._parent_map = {
            'test': 'parent_table'
        }

        # Run
        result = Metadata.get_parents(metadata, 'test')

        # Asserts
        assert result == 'parent_table'

    def test_get_table_meta(self):
        """Test get table meta"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata._metadata = {
            'tables': {
                'test': {'some': 'data'}
            }
        }

        # Run
        result = Metadata.get_table_meta(metadata, 'test')

        # Asserts
        assert result == {'some': 'data'}

    @patch('sdv.metadata._load_csv')
    def test_load_table(self, mock_load_csv):
        """Test load table"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.root_path = 'a/path'
        metadata.get_table_meta.return_value = {'some': 'data'}
        mock_load_csv.return_value = 'data'

        # Run
        result = Metadata.load_table(metadata, 'test')

        # Asserts
        assert result == 'data'

        metadata.get_table_meta.assert_called_once_with('test')
        mock_load_csv.assert_called_once_with('a/path', {'some': 'data'})

    def test_get_dtypes_with_ids(self):
        """Test get data types including ids."""
        # Setup
        table_meta = {
            'fields': {
                'item 0': {'type': 'id', 'subtype': 'integer'},
                'item 1': {'type': 'numerical', 'subtype': 'integer'},
                'item 2': {'type': 'numerical', 'subtype': 'float'},
                'item 3': {'type': 'categorical'},
                'item 4': {'type': 'boolean'},
                'item 5': {'type': 'datetime'}
            },
            'primary_key': 'item 0'
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta
        metadata._DTYPES = Metadata._DTYPES

        # Run
        result = Metadata.get_dtypes(metadata, 'test', ids=True)

        # Asserts
        expected = {
            'item 0': 'int',
            'item 1': 'int',
            'item 2': 'float',
            'item 3': 'object',
            'item 4': 'bool',
            'item 5': 'datetime64',
        }
        assert result == expected

    def test_get_dtypes_no_ids(self):
        """Test get data types excluding ids."""
        # Setup
        table_meta = {
            'fields': {
                'item 0': {'type': 'id', 'subtype': 'integer'},
                'item 1': {'type': 'numerical', 'subtype': 'integer'},
                'item 2': {'type': 'numerical', 'subtype': 'float'},
                'item 3': {'type': 'categorical'},
                'item 4': {'type': 'boolean'},
                'item 5': {'type': 'datetime'},
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta
        metadata._DTYPES = Metadata._DTYPES

        # Run
        result = Metadata.get_dtypes(metadata, 'test')

        # Asserts
        expected = {
            'item 1': 'int',
            'item 2': 'float',
            'item 3': 'object',
            'item 4': 'bool',
            'item 5': 'datetime64',
        }
        assert result == expected

    def test_get_dtypes_error_invalid_type(self):
        """Test get data types with an invalid type."""
        # Setup
        table_meta = {
            'fields': {
                'item': {'type': 'unknown'}
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta
        metadata._DTYPES = Metadata._DTYPES

        # Run
        with pytest.raises(MetadataError):
            Metadata.get_dtypes(metadata, 'test')

    def test_get_dtypes_error_id(self):
        """Test get data types with an id that is not a primary or foreign key."""
        # Setup
        table_meta = {
            'fields': {
                'item': {'type': 'id'}
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta
        metadata._DTYPES = Metadata._DTYPES

        # Run
        with pytest.raises(MetadataError):
            Metadata.get_dtypes(metadata, 'test', ids=True)

    def test_get_dtypes_error_subtype_numerical(self):
        """Test get data types with an invalid numerical subtype."""
        # Setup
        table_meta = {
            'fields': {
                'item': {'type': 'numerical', 'subtype': 'boolean'}
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta
        metadata._DTYPES = Metadata._DTYPES

        # Run
        with pytest.raises(MetadataError):
            Metadata.get_dtypes(metadata, 'test')

    def test_get_dtypes_error_subtype_id(self):
        """Test get data types with an invalid id subtype."""
        # Setup
        table_meta = {
            'fields': {
                'item': {'type': 'id', 'subtype': 'boolean'}
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta
        metadata._DTYPES = Metadata._DTYPES

        # Run
        with pytest.raises(MetadataError):
            Metadata.get_dtypes(metadata, 'test', ids=True)

    def test__get_pii_fields(self):
        """Test get pii fields"""
        # Setup
        table_meta = {
            'fields': {
                'foo': {
                    'type': 'categorical',
                    'pii': True,
                    'pii_category': 'email'
                },
                'bar': {
                    'type': 'categorical',
                    'pii_category': 'email'
                }
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta

        # Run
        result = Metadata._get_pii_fields(metadata, 'test')

        # Asserts
        assert result == {'foo': 'email'}

    @patch('sdv.metadata.transformers.DatetimeTransformer')
    @patch('sdv.metadata.transformers.BooleanTransformer')
    @patch('sdv.metadata.transformers.CategoricalTransformer')
    @patch('sdv.metadata.transformers.NumericalTransformer')
    def test__get_transformers_no_error(self, numerical_mock, categorical_mock,
                                        boolean_mock, datetime_mock):
        """Test get transformers dict for each data type."""
        # Setup
        numerical_mock.return_value = 'NumericalTransformer'
        categorical_mock.return_value = 'CategoricalTransformer'
        boolean_mock.return_value = 'BooleanTransformer'
        datetime_mock.return_value = 'DatetimeTransformer'

        # Run
        dtypes = {
            'integer': 'int',
            'float': 'float',
            'categorical': 'object',
            'boolean': 'bool',
            'datetime': 'datetime64'
        }
        pii_fields = {
            'categorical': 'email'
        }
        result = Metadata._get_transformers(dtypes, pii_fields)

        # Asserts
        expected = {
            'integer': 'NumericalTransformer',
            'float': 'NumericalTransformer',
            'categorical': 'CategoricalTransformer',
            'boolean': 'BooleanTransformer',
            'datetime': 'DatetimeTransformer'
        }
        expected_numerical_calls = [call(dtype=int), call(dtype=float)]

        assert result == expected
        assert len(numerical_mock.call_args_list) == len(expected_numerical_calls)
        for item in numerical_mock.call_args_list:
            assert item in expected_numerical_calls

        assert categorical_mock.call_args == call(anonymize='email')
        assert boolean_mock.call_args == call()
        assert datetime_mock.call_args == call()

    def test__get_transformers_raise_valueerror(self):
        """Test get transformers dict raise ValueError."""
        # Run
        dtypes = {
            'void': 'void'
        }
        with pytest.raises(ValueError):
            Metadata._get_transformers(dtypes, None)

    @patch('sdv.metadata.HyperTransformer')
    def test__load_hyper_transformer(self, mock_ht):
        """Test load HyperTransformer"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_dtypes.return_value = {'meta': 'dtypes'}
        metadata._get_pii_fields.return_value = {'meta': 'pii_fields'}
        metadata._get_transformers.return_value = {'meta': 'transformers'}
        mock_ht.return_value = 'hypertransformer'

        # Run
        result = Metadata._load_hyper_transformer(metadata, 'test')

        # Asserts
        assert result == 'hypertransformer'
        metadata.get_dtypes.assert_called_once_with('test')
        metadata._get_pii_fields.assert_called_once_with('test')
        metadata._get_transformers.assert_called_once_with(
            {'meta': 'dtypes'},
            {'meta': 'pii_fields'}
        )
        mock_ht.assert_called_once_with(transformers={'meta': 'transformers'})

    def test_get_tables(self):
        """Test get table names"""
        # Setup
        _metadata = {
            'tables': {
                'table 1': None,
                'table 2': None,
                'table 3': None
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata._metadata = _metadata

        # Run
        result = Metadata.get_tables(metadata)

        # Asserts
        assert sorted(result) == ['table 1', 'table 2', 'table 3']

    def test_load_tables(self):
        """Test get tables"""
        # Setup
        table_names = ['foo', 'bar', 'tar']
        table_data = [
            pd.DataFrame({'foo': [1, 2]}),
            pd.DataFrame({'bar': [3, 4]}),
            pd.DataFrame({'tar': [5, 6]})
        ]
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.side_effect = table_names
        metadata.load_table.side_effect = table_data

        # Run
        tables = ['table 1', 'table 2', 'table 3']
        result = Metadata.load_tables(metadata, tables=tables)

        # Asserts
        expected = {
            'table 1': pd.DataFrame({'foo': [1, 2]}),
            'table 2': pd.DataFrame({'bar': [3, 4]}),
            'table 3': pd.DataFrame({'tar': [5, 6]})
        }
        assert result.keys() == expected.keys()

        for k, v in result.items():
            pd.testing.assert_frame_equal(v, expected[k])

    def test_get_fields(self):
        """Test get fields"""
        # Setup
        table_meta = {
            'fields': {
                'a_field': 'some data',
                'b_field': 'other data'
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta

        # Run
        result = Metadata.get_fields(metadata, 'test')

        # Asserts
        expected = {'a_field': 'some data', 'b_field': 'other data'}
        assert result == expected

        metadata.get_table_meta.assert_called_once_with('test')

    def test_get_primary_key(self):
        """Test get primary key"""
        # Setup
        table_meta = {
            'primary_key': 'a_primary_key'
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_table_meta.return_value = table_meta

        # Run
        result = Metadata.get_primary_key(metadata, 'test')

        # Asserts
        assert result == 'a_primary_key'
        metadata.get_table_meta.assert_called_once_with('test')

    def test_get_foreign_key(self):
        """Test get foreign key"""
        # Setup
        primary_key = 'a_primary_key'
        fields = {
            'a_field': {
                'ref': {
                    'field': 'a_primary_key'
                },
                'name': 'a_field'
            },
            'p_field': {
                'ref': {
                    'field': 'another_key_field'
                },
                'name': 'p_field'
            }
        }
        metadata = Mock(spec_set=Metadata)
        metadata.get_primary_key.return_value = primary_key
        metadata.get_fields.return_value = fields

        # Run
        result = Metadata.get_foreign_key(metadata, 'parent', 'child')

        # Asserts
        assert result == 'a_field'
        metadata.get_primary_key.assert_called_once_with('parent')
        metadata.get_fields.assert_called_once_with('child')

    def test_reverse_transform(self):
        """Test reverse transform"""
        # Setup
        ht_mock = Mock()
        ht_mock.reverse_transform.return_value = {
            'item 1': pd.Series([1.0, 2.0, None, 4.0, 5.0]),
            'item 2': pd.Series([1.1, None, 3.3, None, 5.5]),
            'item 3': pd.Series([None, 'bbb', 'ccc', 'ddd', None]),
            'item 4': pd.Series([True, False, None, False, True])
        }

        metadata = Mock(spec_set=Metadata)
        metadata._hyper_transformers = {
            'test': ht_mock
        }
        metadata.get_dtypes.return_value = {
            'item 1': 'int',
            'item 2': 'float',
            'item 3': 'str',
            'item 4': 'bool',
        }

        # Run
        data = pd.DataFrame({'foo': [0, 1]})
        Metadata.reverse_transform(metadata, 'test', data)

        # Asserts
        expected_call = pd.DataFrame({'foo': [0, 1]})
        pd.testing.assert_frame_equal(
            ht_mock.reverse_transform.call_args[0][0],
            expected_call
        )

    def test_add_table_already_exist(self):
        """Try to add a new table that already exist"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']

        # Run
        with pytest.raises(ValueError):
            Metadata.add_table(metadata, 'a_table')

    def test_add_table_only_name(self):
        """Add table with only the name"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}

        # Run
        Metadata.add_table(metadata, 'x_table')

        # Asserts
        expected_table_meta = {
            'fields': dict()
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

        metadata.set_primary_key.call_count == 0
        metadata.add_relationship.call_count == 0

    def test_add_table_with_primary_key(self):
        """Add table with primary key"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}

        # Run
        Metadata.add_table(metadata, 'x_table', primary_key='id')

        # Asserts
        expected_table_meta = {
            'fields': dict()
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

        metadata.set_primary_key.assert_called_once_with('x_table', 'id')
        metadata.add_relationship.call_count == 0

    def test_add_table_with_foreign_key(self):
        """Add table with foreign key"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}

        # Run
        Metadata.add_table(metadata, 'x_table', parent='users')

        # Asserts
        expected_table_meta = {
            'fields': dict()
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

        metadata.set_primary_key.call_count == 0
        metadata.add_relationship.assert_called_once_with('users', 'x_table', None)

    def test_add_table_with_fields_metadata(self):
        """Add table with fields metadata"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}

        # Run
        fields_metadata = {
            'a_field': {'type': 'numerical', 'subtype': 'integer'}
        }

        Metadata.add_table(metadata, 'x_table', fields_metadata=fields_metadata)

        # Asserts
        expected_table_meta = {
            'fields': {
                'a_field': {'type': 'numerical', 'subtype': 'integer'}
            }
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

        metadata.set_primary_key.call_count == 0
        metadata.add_relationship.call_count == 0

    def test_add_table_with_fields_no_data(self):
        """Add table with fields and no data"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}

        # Run
        fields = ['a_field', 'b_field']

        Metadata.add_table(metadata, 'x_table', fields=fields)

        # Asserts
        expected_table_meta = {
            'fields': dict()
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

    def test_add_table_with_fields_data(self):
        """Add table with fields and data"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}
        metadata._get_field_details.return_value = {
            'a_field': {'type': 'numerical', 'subtype': 'integer'},
            'b_field': {'type': 'boolean'}
        }

        # Run
        fields = ['a_field', 'b_field']
        data = pd.DataFrame({'a_field': [0, 1], 'b_field': [True, False], 'c_field': ['a', 'b']})

        Metadata.add_table(metadata, 'x_table', fields=fields, data=data)

        # Asserts
        expected_table_meta = {
            'fields': {
                'a_field': {'type': 'numerical', 'subtype': 'integer'},
                'b_field': {'type': 'boolean'}
            }
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

        metadata.set_primary_key.call_count == 0
        metadata.add_relationship.call_count == 0

    def test_add_table_with_no_fields_data(self):
        """Add table with data to analyze all"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}
        metadata._get_field_details.return_value = {
            'a_field': {'type': 'numerical', 'subtype': 'integer'},
            'b_field': {'type': 'boolean'},
            'c_field': {'type': 'categorical'}
        }

        # Run
        data = pd.DataFrame({'a_field': [0, 1], 'b_field': [True, False], 'c_field': ['a', 'b']})

        Metadata.add_table(metadata, 'x_table', data=data)

        # Asserts
        expected_table_meta = {
            'fields': {
                'a_field': {'type': 'numerical', 'subtype': 'integer'},
                'b_field': {'type': 'boolean'},
                'c_field': {'type': 'categorical'}
            }
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

        metadata.set_primary_key.call_count == 0
        metadata.add_relationship.call_count == 0

    @patch('sdv.metadata.pd.read_csv')
    def test_add_table_with_data_str(self, mock_read_csv):
        """Add table with data as str"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata._metadata = {'tables': dict()}
        mock_read_csv.return_value = pd.DataFrame({
            'a_field': [0, 1],
            'b_field': [True, False],
            'c_field': ['a', 'b']
        })
        metadata._get_field_details.return_value = {
            'a_field': {'type': 'numerical', 'subtype': 'integer'},
            'b_field': {'type': 'boolean'},
            'c_field': {'type': 'categorical'}
        }

        # Run
        Metadata.add_table(metadata, 'x_table', data='/path/to/file.csv')

        expected_table_meta = {
            'fields': {
                'a_field': {'type': 'numerical', 'subtype': 'integer'},
                'b_field': {'type': 'boolean'},
                'c_field': {'type': 'categorical'}
            },
            'path': '/path/to/file.csv'
        }

        assert metadata._metadata['tables']['x_table'] == expected_table_meta

        metadata.set_primary_key.call_count == 0
        metadata.add_relationship.call_count == 0

    def test_add_relationship_table_no_exist(self):
        """Add relationship table no exist"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = list()

        # Run
        with pytest.raises(ValueError):
            Metadata.add_relationship(metadata, 'a_table', 'b_table')

    def test_add_relationship_parent_no_exist(self):
        """Add relationship table no exist"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table']

        # Run
        with pytest.raises(ValueError):
            Metadata.add_relationship(metadata, 'a_table', 'b_table')

    def test_add_relationship_already_exist(self):
        """Add relationship already exist"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata.get_parents.return_value = set(['b_table'])

        # Run
        with pytest.raises(ValueError):
            Metadata.add_relationship(metadata, 'a_table', 'b_table')

    def test_add_relationship_parent_no_primary_key(self):
        """Add relationship parent no primary key"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = ['a_table', 'b_table']
        metadata.get_parents.return_value = set()
        metadata.get_children.return_value = set()
        metadata.get_primary_key.return_value = None

        # Run
        with pytest.raises(ValueError):
            Metadata.add_relationship(metadata, 'a_table', 'b_table')

    def test_set_primary_key(self):
        """Set primary key table no exist"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = list()
        metadata.get_fields.return_value = {'a_field': {'type': 'id', 'subtype': 'integer'}}
        metadata._metadata = {
            'tables': {
                'a_table': {
                    'fields': {'a_field': {'type': 'id', 'subtype': 'integer'}}
                }
            }
        }

        # Run
        Metadata.set_primary_key(metadata, 'a_table', 'a_field')

        # Asserts
        metadata._check_field.assert_called_once_with('a_table', 'a_field', exists=True)
        metadata.get_fields.assert_called_once_with('a_table')
        metadata._get_key_subtype.assert_called_once_with({'type': 'id', 'subtype': 'integer'})

    def test_add_field(self):
        """Add field table no exist"""
        # Setup
        metadata = Mock(spec_set=Metadata)
        metadata.get_tables.return_value = list()
        metadata._metadata = {
            'tables': {
                'a_table': {'fields': dict()}
            }
        }

        # Run
        Metadata.add_field(metadata, 'a_table', 'a_field', 'id', 'string', None)

        # Asserts
        expected_metadata = {
            'tables': {
                'a_table': {
                    'fields': {'a_field': {'type': 'id', 'subtype': 'string'}}
                }
            }
        }

        assert metadata._metadata == expected_metadata
        metadata._check_field.assert_called_once_with('a_table', 'a_field', exists=False)

    def test__get_graphviz_extension_path_without_extension(self):
        """Raises a ValueError when the path doesn't contains an extension."""
        with pytest.raises(ValueError):
            Metadata._get_graphviz_extension('/some/path')

    def test__get_graphviz_extension_invalid_extension(self):
        """Raises a ValueError when the path contains an invalid extension."""
        with pytest.raises(ValueError):
            Metadata._get_graphviz_extension('/some/path.foo')

    def test__get_graphviz_extension_none(self):
        """Get graphviz with path equals to None."""
        # Run
        result = Metadata._get_graphviz_extension(None)

        # Asserts
        assert result == (None, None)

    def test__get_graphviz_extension_valid(self):
        """Get a valid graphviz extension."""
        # Run
        result = Metadata._get_graphviz_extension('/some/path.png')

        # Asserts
        assert result == ('/some/path', 'png')

    def test__visualize_add_nodes(self):
        """Add nodes into a graphviz digraph."""
        # Setup
        metadata = MagicMock(spec_set=Metadata)
        minimock = Mock()

        # pass tests in python3.5
        minimock.items.return_value = (
            ('a_field', {'type': 'numerical', 'subtype': 'integer'}),
            ('b_field', {'type': 'id'}),
            ('c_field', {'type': 'id', 'ref': {'table': 'other', 'field': 'pk_field'}})
        )

        metadata.get_tables.return_value = ['demo']
        metadata.get_fields.return_value = minimock

        metadata.get_primary_key.return_value = 'b_field'
        metadata.get_parents.return_value = set(['other'])
        metadata.get_foreign_key.return_value = 'c_field'

        metadata.get_table_meta.return_value = {'path': None}

        plot = Mock()

        # Run
        Metadata._visualize_add_nodes(metadata, plot)

        # Asserts
        expected_node_label = r"{demo|a_field : numerical - integer\lb_field : id\l" \
                              r"c_field : id\l|Primary key: b_field\l" \
                              r"Foreign key (other): c_field\l}"

        metadata.get_fields.assert_called_once_with('demo')
        metadata.get_primary_key.assert_called_once_with('demo')
        metadata.get_parents.assert_called_once_with('demo')
        metadata.get_table_meta.assert_called_once_with('demo')
        metadata.get_foreign_key.assert_called_once_with('other', 'demo')
        metadata.get_table_meta.assert_called_once_with('demo')

        plot.node.assert_called_once_with('demo', label=expected_node_label)

    def test__visualize_add_edges(self):
        """Add edges into a graphviz digraph."""
        # Setup
        metadata = MagicMock(spec_set=Metadata)

        metadata.get_tables.return_value = ['demo', 'other']
        metadata.get_parents.side_effect = [set(['other']), set()]

        metadata.get_foreign_key.return_value = 'fk'
        metadata.get_primary_key.return_value = 'pk'

        plot = Mock()

        # Run
        Metadata._visualize_add_edges(metadata, plot)

        # Asserts
        expected_edge_label = '   {}.{} -> {}.{}'.format('demo', 'fk', 'other', 'pk')

        metadata.get_tables.assert_called_once_with()
        metadata.get_foreign_key.assert_called_once_with('other', 'demo')
        metadata.get_primary_key.assert_called_once_with('other')
        assert metadata.get_parents.call_args_list == [call('demo'), call('other')]

        plot.edge.assert_called_once_with(
            'other',
            'demo',
            label=expected_edge_label,
            arrowhead='crow'
        )

    @patch('sdv.metadata.graphviz')
    def test_visualize(self, graphviz_mock):
        """Metadata visualize digraph"""
        # Setup
        plot = Mock(spec_set=graphviz.Digraph)
        graphviz_mock.Digraph.return_value = plot

        metadata = MagicMock(spec_set=Metadata)
        metadata._get_graphviz_extension.return_value = ('output', 'png')

        # Run
        Metadata.visualize(metadata, path='output.png')

        # Asserts
        metadata._get_graphviz_extension.assert_called_once_with('output.png')
        metadata._visualize_add_nodes.assert_called_once_with(plot)
        metadata._visualize_add_edges.assert_called_once_with(plot)

        plot.render.assert_called_once_with(filename='output', cleanup=True, format='png')