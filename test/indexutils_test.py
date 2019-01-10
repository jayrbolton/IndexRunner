# -*- coding: utf-8 -*-
import unittest
from nose.plugins.attrib import attr

import os  # noqa: F401
import json  # noqa: F401
from unittest.mock import patch, Mock

from os import environ
from configparser import ConfigParser  # py3
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from IndexRunner.IndexerUtils import IndexerUtils
import datetime


class IndexerTester(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.token = environ.get('KB_AUTH_TOKEN', None)
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('IndexRunner'):
            cls.cfg[nameval[0]] = nameval[1]
        cls.scratch = cls.cfg['scratch']
        cls.cfg['token'] = cls.token
        cls.cfg['kafka-server'] = None
        cls.test_dir = os.path.dirname(os.path.abspath(__file__))
        cls.mock_dir = os.path.join(cls.test_dir, 'mock_data')
        cls.es = Elasticsearch(cls.cfg['elastic-host'])

        cls.wsinfo = cls.read_mock('get_workspace_info.json')
        cls.wslist = cls.read_mock('list_objects.json')
        cls.narobj = cls.read_mock('narrative_object.json')
        cls.genobj = cls.read_mock('genome_object_nodata.json')
        cls.geninfo = cls.read_mock('genome_object_info.json')
        cls.new_version_event = {
            'strcde': 'WS',
            'accgrp': 1,
            'objid': '2',
            'ver': 3,
            'newname': None,
            'evtype': 'NEW_VERSION',
            'time': '2018-02-08T23:23:25.553Z',
            'objtype': 'KBaseNarrative.Narrative',
            'objtypever': 4,
            'public': False
            }

    @classmethod
    def read_mock(cls, filename):
        with open(os.path.join(cls.mock_dir, filename)) as f:
            obj = json.loads(f.read())
        return obj

    def reset(self):
        for i in ['genome', 'genomefeature']:
            try:
                if self.es.indices.exists(index=i):
                    self.es.indices.delete(index=i)
            except:
                pass

    def _init_es_genome(self):
        self.reset()
        with open(os.path.join(self.mock_dir, 'genome-es-map.json')) as f:
            d = json.loads(f.read())

        indices = d.keys()
        for index in indices:
            schema = d[index]
            schema.pop('settings')
            self.es.indices.create(index=index, body=schema)
        with open(os.path.join(self.mock_dir, 'genome-es.json')) as f:
            d = json.loads(f.read())['hits']['hits']
        bulk(self.es, d)
        for index in indices:
            self.es.indices.refresh(index=index)

    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    @patch('IndexRunner.MethodRunner.Catalog', autospec=True)
    def index_object_test(self, mock_wsa, mock_cat):
        iu = IndexerUtils(self.cfg)
        iu.ws.get_workspace_info.return_value = self.wsinfo
        # iu.ws.get_objects2.return_value = {'data': [self.narobj]}
        iu.ws.get_objects2.return_value = self.narobj
        iu.ws.list_objects.return_value = []
        rv = {'docker_img_name': 'mock_indexer:latest'}
        iu.mr.catalog.get_module_version.return_value = rv
        event = self.new_version_event.copy()
        event['upa'] = '1/2/3'
        res = iu.new_object_version(event)
        self.assertIsNotNone(res)

    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    @patch('IndexRunner.MethodRunner.Catalog', autospec=True)
    def index_request_test(self, mock_wsa, mock_cat):
        iu = IndexerUtils(self.cfg)
        iu.ws.get_workspace_info.return_value = self.wsinfo
        iu.ws.get_objects2.return_value = self.genobj
        iu.ws.list_objects.return_value = []
        rv = {'docker_img_name': 'mock_indexer:latest'}
        iu.mr.catalog.get_module_version.return_value = rv
        ev = self.new_version_event.copy()
        ev['objtype'] = 'KBaseGenomes.Genome'
        ev['objid'] = '3'
        id = 'WS:1:3:3'
        self.reset()
        iu.process_event(ev)
        res = self.es.get(index='genome', routing=id, doc_type='data', id=id)
        self.assertIsNotNone(res)

    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    @patch('IndexRunner.MethodRunner.Catalog', autospec=True)
    def index_new_all_test(self, mock_wsa, mock_cat):
        iu = IndexerUtils(self.cfg)
        iu.ws.get_workspace_info.return_value = self.wsinfo
        iu.ws.get_objects2.return_value = self.genobj
        iu.ws.list_objects.return_value = []
        iu.ws.get_object_info3.return_value = self.geninfo
        rv = {'docker_img_name': 'mock_indexer:latest'}
        iu.mr.catalog.get_module_version.return_value = rv
        ev = self.new_version_event.copy()
        ev['objtype'] = None
        ev['objid'] = '3'
        ev['evtype'] = 'NEW_ALL_VERSIONS'
        ev['ver'] = None
        id = 'WS:1:3:3'
        self.reset()
        iu.process_event(ev)
        res = self.es.get(index='genome', routing=id, doc_type='data', id=id)
        self.assertIsNotNone(res)
        self.assertIn('ojson', res['_source'])
        self.assertTrue(res['_source']['islast'])

    @attr('online')
    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    @patch('IndexRunner.MethodRunner.Catalog', autospec=True)
    def index_request_genome_test(self, mock_wsa, mock_cat):
        iu = IndexerUtils(self.cfg)
        iu.ws.get_workspace_info.return_value = self.wsinfo
        # iu.ws.get_objects2.return_value = self.genobj
        iu.ws.list_objects.return_value = []
        iu.ws.get_object_info3.return_value = self.geninfo
        rv = {'docker_img_name': 'test/kb_genomeindexer:latest'}
        iu.mr.catalog.get_module_version.return_value = rv
        ev = self.new_version_event.copy()
        ev['objtype'] = 'KBaseGenomes.Genome'
        ev['objid'] = '2'
        ev['accgrp'] = 15792
        ev['ver'] = 1
        id = 'WS:15792:2:1'
        self.reset()
        iu.process_event(ev)
        res = self.es.get(index='genome', routing=id, doc_type='data', id=id)
        self.assertIsNotNone(res)
        fid = 'WS:15792:2:1:L876_RS0116375'
        res = self.es.get(index='genomefeature', routing=id,
                          doc_type='data', id=fid)
        self.assertIsNotNone(res)
        self.assertIn('ojson', res['_source'])
        self.assertTrue(res['_source']['islast'])

    def index_error_test(self):
        iu = IndexerUtils(self.cfg)
        if os.path.exists('error.log'):
            os.remove('error.log')
        iu._new_object_version_index = Mock(side_effect=KeyError())
        iu._new_object_version_feature_index = Mock(side_effect=KeyError())
        ev = self.new_version_event.copy()
        iu.process_event(ev)
        self.assertTrue(os.path.exists('error.log'))

    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    def publish_test(self, ws_mock):
        """
        Publish and unpublish tests
        """
        # PUBLISH_ALL_VERSIONS,
        # PUBLISH_ACCESS_GROUP,
        # UNPUBLISH_ALL_VERSIONS,
        # UNPUBLISH_ACCESS_GROUP,
        mwsi = [1,
                "auser:narrative_1485560571814",
                "auser",
                "2018-10-18T00:12:42+0000",
                25,
                "a",
                "y",
                "unlocked",
                {"narrative_nice_name": "A Fancy Nasrrative",
                 "is_temporary": "false",
                 "data_palette_id": "22", "narrative": "23"
                 }
                ]

        self._init_es_genome()
        ev = {
            "strcde": "WS",
            "accgrp": 1,
            "objid": None,
            "ver": None,
            "newname": None,
            "time": datetime.datetime.utcnow(),
            "evtype": "PUBLISH_ACCESS_GROUP",
            "objtype": None,
            "objtypever": None,
            "public": None
        }
        iu = IndexerUtils(self.cfg)
        iu.ws.get_workspace_info.return_value = mwsi
        iu.process_event(ev)
        # Check that accgrp changed
        id = 'WS:1:3:3'
        res = self.es.get(index='genome', routing=id, doc_type='access',
                          id=id)
        self.assertIn(-1, res['_source']['groups'])
        res = self.es.get(index='genome', routing=id, doc_type='data',
                          id=id)
        self.assertTrue(res['_source']['public'])
        #
        ev['evtype'] = "UNPUBLISH_ACCESS_GROUP"
        mwsi[6] = 'n'
        iu = IndexerUtils(self.cfg)
        iu.ws.get_workspace_info.return_value = mwsi
        iu.process_event(ev)
        # Check that accgrp changed
        id = 'WS:1:3:3'
        res = self.es.get(index='genome', routing=id, doc_type='access',
                          id=id)
        self.assertNotIn(-1, res['_source']['groups'])
        res = self.es.get(index='genome', routing=id, doc_type='data',
                          id=id)
        self.assertFalse(res['_source']['public'])

    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    def delete_event_test(self, mock_ws):
        # DELETE_ALL_VERSIONS,
        # UNDELETE_ALL_VERSIONS,
        # DELETE_ACCESS_GROUP,
        self._init_es_genome()
        ev = self.new_version_event.copy()
        ev['evtype'] = 'DELETE_ALL_VERSIONS'
        ev['objid'] = '3'
        iu = IndexerUtils(self.cfg)
        iu.process_event(ev)
        id = 'WS:1:3:3'
        res = self.es.get(index='genome', routing=id, doc_type='data',
                          id=id, ignore=404)
        self.assertFalse(res['found'])
        #
        ev = self.new_version_event.copy()
        ev['evtype'] = 'UNDELETE_ALL_VERSIONS'
        iu = IndexerUtils(self.cfg)
        # iu.process_event(ev)

    def rename_event_test(self):
        # RENAME_ALL_VERSIONS,
        ev = self.new_version_event.copy()
        ev['evtype'] = 'RENAME_ALL_VERSIONS'
        ev['objid'] = '3'
        iu = IndexerUtils(self.cfg)
        iu.process_event(ev)
        # TODO

    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    @patch('IndexRunner.IndexerUtils.EventProducer', autospec=True)
    def copy_event_test(self, mock_ep, mock_ws):
        # COPY_ACCESS_GROUP;
        ev = {
            "strcde": "WS",
            "accgrp": 1,
            "objid": None,
            "ver": None,
            "newname": None,
            "time": datetime.datetime.utcnow(),
            "evtype": "COPY_ACCESS_GROUP",
            "objtype": None,
            "objtypever": None,
            "public": False
        }
        iu = IndexerUtils(self.cfg)
        iu.ws.list_objects.return_value = self.wslist
        iu.process_event(ev)
        iu.ep.index_objects.assert_called()

    @patch('IndexRunner.IndexerUtils.WorkspaceAdminUtil', autospec=True)
    @patch('IndexRunner.IndexerUtils.EventProducer', autospec=True)
    def reindex_event_test(self, mock_ep, mock_ws):
        ev = {
            "strcde": "WS",
            "accgrp": 1,
            "objid": None,
            "ver": None,
            "newname": None,
            "time": datetime.datetime.utcnow(),
            "evtype": "REINDEX_WORKSPACE",
            "objtype": None,
            "objtypever": None,
            "public": False
        }
        iu = IndexerUtils(self.cfg)
        iu.ws.list_objects.return_value = self.wslist
        iu.process_event(ev)
        iu.ep.index_objects.assert_called()
