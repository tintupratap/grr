#!/usr/bin/env python
# -*- mode: python; encoding: utf-8 -*-

from google.protobuf import text_format
import unittest
from grr.lib import rdfvalue
from grr.lib.rdfvalues import objects
from grr_response_proto import objects_pb2


def MakeClient():
  client = objects.ClientSnapshot(client_id="C.0000000000000000")

  base_pb = objects_pb2.ClientSnapshot()
  text_format.Merge("""
    os_release: "Ubuntu"
    os_version: "14.4"
    interfaces: {
      addresses: {
        address_type: INET
        packed_bytes: "\177\000\000\001"
      }
      addresses: {
        address_type: INET6
        packed_bytes: "\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\001"
      }
    }
    interfaces: {
    mac_address: "\001\002\003\004\001\002\003\004\001\002\003\004"
      addresses: {
        address_type: INET
        packed_bytes: "\010\010\010\010"
      }
      addresses: {
        address_type: INET6
        packed_bytes: "\376\200\001\002\003\000\000\000\000\000\000\000\000\000\000\000"
      }
    }
    knowledge_base: {
      users: {
        username: "joe"
        full_name: "Good Guy Joe"
      }
      users: {
        username: "fred"
        full_name: "Ok Guy Fred"
      }
      fqdn: "test123.examples.com"
      os: "Linux"
    }
    cloud_instance: {
      cloud_type: GOOGLE
      google: {
        unique_id: "us-central1-a/myproject/1771384456894610289"
      }
    }
    """, base_pb)

  client.ParseFromString(base_pb.SerializeToString())
  return client


class ObjectTest(unittest.TestCase):

  def testInvalidClientID(self):

    # No id.
    with self.assertRaises(ValueError):
      objects.ClientSnapshot()

    # One digit short.
    with self.assertRaises(ValueError):
      objects.ClientSnapshot(client_id="C.000000000000000")

    with self.assertRaises(ValueError):
      objects.ClientSnapshot(client_id="not a real id")

    objects.ClientSnapshot(client_id="C.0000000000000000")

  def testClientBasics(self):
    client = MakeClient()
    self.assertIsNone(client.timestamp)

    self.assertEqual(client.knowledge_base.fqdn, "test123.examples.com")
    self.assertEqual(client.Uname(), "Linux-Ubuntu-14.4")

  def testClientAddresses(self):
    client = MakeClient()
    self.assertEqual(
        sorted(client.GetIPAddresses()), ["8.8.8.8", "fe80:102:300::"])
    self.assertEqual(client.GetMacAddresses(), ["010203040102030401020304"])

  def testClientSummary(self):
    client = MakeClient()
    summary = client.GetSummary()
    self.assertEqual(summary.system_info.fqdn, "test123.examples.com")
    self.assertEqual(summary.cloud_instance_id,
                     "us-central1-a/myproject/1771384456894610289")
    self.assertEqual(
        sorted([u.username for u in summary.users]), ["fred", "joe"])

  def testClientSummaryTimestamp(self):
    client = MakeClient()
    client.timestamp = rdfvalue.RDFDatetime.Now()
    summary = client.GetSummary()
    self.assertEqual(client.timestamp, summary.timestamp)


class PathIDTest(unittest.TestCase):

  def testEquality(self):
    foo = objects.PathID(["quux", "norf"])
    bar = objects.PathID(["quux", "norf"])

    self.assertIsNot(foo, bar)
    self.assertEqual(foo, bar)

  def testInequality(self):
    foo = objects.PathID(["quux", "foo"])
    bar = objects.PathID(["quux", "bar"])

    self.assertIsNot(foo, bar)
    self.assertNotEqual(foo, bar)

  def testHash(self):
    quuxes = dict()
    quuxes[objects.PathID(["foo", "bar"])] = 4
    quuxes[objects.PathID(["foo", "baz"])] = 8
    quuxes[objects.PathID(["norf"])] = 15
    quuxes[objects.PathID(["foo", "bar"])] = 16
    quuxes[objects.PathID(["norf"])] = 23
    quuxes[objects.PathID(["thud"])] = 42

    self.assertEqual(quuxes[objects.PathID(["foo", "bar"])], 16)
    self.assertEqual(quuxes[objects.PathID(["foo", "baz"])], 8)
    self.assertEqual(quuxes[objects.PathID(["norf"])], 23)
    self.assertEqual(quuxes[objects.PathID(["thud"])], 42)

  def testRepr(self):
    string = str(objects.PathID(["foo", "bar", "baz"]))
    self.assertRegexpMatches(string, r"^PathID\(\'[0-9a-f]{64}\'\)$")

  def testReprEmpty(self):
    string = str(objects.PathID([]))
    self.assertEqual(string, "PathID('{}')".format("0" * 64))


class PathInfoTest(unittest.TestCase):

  def testRootPathDirectoryValidation(self):
    with self.assertRaises(AssertionError):
      objects.PathInfo(components=[])

  def testGetParentNonRoot(self):
    path_info = objects.PathInfo.TSK(components=["foo", "bar"], directory=False)

    parent_path_info = path_info.GetParent()
    self.assertIsNotNone(parent_path_info)
    self.assertEqual(parent_path_info.components, ["foo"])
    self.assertEqual(parent_path_info.path_type, objects.PathInfo.PathType.TSK)
    self.assertEqual(parent_path_info.directory, True)

  def testGetParentAlmostRoot(self):
    path_info = objects.PathInfo.OS(components=["foo"], directory=False)

    parent_path_info = path_info.GetParent()
    self.assertIsNotNone(parent_path_info)
    self.assertEqual(parent_path_info.components, [])
    self.assertEqual(parent_path_info.path_type, objects.PathInfo.PathType.OS)
    self.assertTrue(parent_path_info.root)
    self.assertTrue(parent_path_info.directory)

  def testGetParentRoot(self):
    path_info = objects.PathInfo.Registry(components=[], directory=True)

    self.assertIsNone(path_info.GetParent())

  def testGetAncestorsEmpty(self):
    path_info = objects.PathInfo(components=[], directory=True)
    self.assertEqual(list(path_info.GetAncestors()), [])

  def testGetAncestorsRoot(self):
    path_info = objects.PathInfo(components=["foo"])

    results = list(path_info.GetAncestors())
    self.assertEqual(len(results), 1)
    self.assertEqual(results[0].components, [])

  def testGetAncestorsOrder(self):
    path_info = objects.PathInfo(components=["foo", "bar", "baz", "quux"])

    results = list(path_info.GetAncestors())
    self.assertEqual(len(results), 4)
    self.assertEqual(results[0].components, ["foo", "bar", "baz"])
    self.assertEqual(results[1].components, ["foo", "bar"])
    self.assertEqual(results[2].components, ["foo"])
    self.assertEqual(results[3].components, [])

  def testUpdateFromValidatesType(self):
    with self.assertRaises(TypeError):
      objects.PathInfo(
          components=["usr", "local", "bin"],).UpdateFrom("/usr/local/bin")

  def testUpdateFromValidatesPathType(self):
    with self.assertRaises(ValueError):
      objects.PathInfo.OS(components=["usr", "local", "bin"]).UpdateFrom(
          objects.PathInfo.TSK(components=["usr", "local", "bin"]))

  def testUpdateFromValidatesComponents(self):
    with self.assertRaises(ValueError):
      objects.PathInfo(components=["usr", "local", "bin"]).UpdateFrom(
          objects.PathInfo(components=["usr", "local", "bin", "protoc"]))

  def testUpdateFromDirectory(self):
    dest = objects.PathInfo(components=["usr", "local", "bin"])
    self.assertFalse(dest.directory)
    dest.UpdateFrom(
        objects.PathInfo(components=["usr", "local", "bin"], directory=True))
    self.assertTrue(dest.directory)

  def testMergePathInfoLastUpdate(self):
    components = ["usr", "local", "bin"]
    dest = objects.PathInfo(components=components)
    self.assertIsNone(dest.last_path_history_timestamp)

    dest.UpdateFrom(
        objects.PathInfo(
            components=components,
            last_path_history_timestamp=rdfvalue.RDFDatetime.FromHumanReadable(
                "2017-01-01")))
    self.assertEqual(dest.last_path_history_timestamp,
                     rdfvalue.RDFDatetime.FromHumanReadable("2017-01-01"))

    # Merging in a record without last_path_history_timestamp shouldn't change
    # it.
    dest.UpdateFrom(objects.PathInfo(components=components))
    self.assertEqual(dest.last_path_history_timestamp,
                     rdfvalue.RDFDatetime.FromHumanReadable("2017-01-01"))

    # Merging in a record with an earlier last_path_history_timestamp shouldn't
    # change it.
    dest.UpdateFrom(
        objects.PathInfo(
            components=components,
            last_path_history_timestamp=rdfvalue.RDFDatetime.FromHumanReadable(
                "2016-01-01")))
    self.assertEqual(dest.last_path_history_timestamp,
                     rdfvalue.RDFDatetime.FromHumanReadable("2017-01-01"))

    # Merging in a record with a later last_path_history_timestamp should change
    # it.
    dest.UpdateFrom(
        objects.PathInfo(
            components=components,
            last_path_history_timestamp=rdfvalue.RDFDatetime.FromHumanReadable(
                "2018-01-01")))
    self.assertEqual(dest.last_path_history_timestamp,
                     rdfvalue.RDFDatetime.FromHumanReadable("2018-01-01"))


if __name__ == "__main__":
  unittest.main()
