from binascii import hexlify
import hashlib
from importlib.util import find_spec
import warnings

import pytest

from passlib.exc import UnknownHashError
from tests.utils import TestCase, hb

from passlib.crypto.digest import pbkdf2_hmac, PBKDF2_BACKENDS
import re


class HashInfoTest(TestCase):
    """test various crypto functions"""

    descriptionPrefix = "passlib.crypto.digest"

    #: list of formats norm_hash_name() should support
    norm_hash_formats = ["hashlib", "iana"]

    #: test cases for norm_hash_name()
    #: each row contains (iana name, hashlib name, ... 0+ unnormalized names)
    norm_hash_samples = [
        # real hashes
        ("md5", "md5", "SCRAM-MD5-PLUS", "MD-5"),
        ("sha1", "sha-1", "SCRAM-SHA-1", "SHA1"),
        ("sha256", "sha-256", "SHA_256", "sha2-256"),
        (
            "ripemd160",
            "ripemd-160",
            "SCRAM-RIPEMD-160",
            "RIPEmd160",
            # NOTE: there was an older "RIPEMD" & "RIPEMD-128", but python treates "RIPEMD"
            #       as alias for "RIPEMD-160"
            "ripemd",
            "SCRAM-RIPEMD",
        ),
        # fake hashes (to check if fallback normalization behaves sanely)
        ("sha4_256", "sha4-256", "SHA4-256", "SHA-4-256"),
        ("test128", "test-128", "TEST128"),
        ("test2", "test2", "TEST-2"),
        ("test3_128", "test3-128", "TEST-3-128"),
    ]

    def test_norm_hash_name(self):
        """norm_hash_name()"""
        from itertools import chain
        from passlib.crypto.digest import norm_hash_name, _known_hash_names

        # snapshot warning state, ignore unknown hash warnings
        ctx = warnings.catch_warnings()
        ctx.__enter__()
        self.addCleanup(ctx.__exit__)
        warnings.filterwarnings("ignore", ".*unknown hash")
        warnings.filterwarnings("ignore", ".*unsupported hash")

        # test string types
        assert norm_hash_name("MD4") == "md4"
        assert norm_hash_name(b"MD4") == "md4"
        with pytest.raises(TypeError):
            norm_hash_name(None)

        # test selected results
        for row in chain(_known_hash_names, self.norm_hash_samples):
            for idx, format in enumerate(self.norm_hash_formats):
                correct = row[idx]
                for value in row:
                    result = norm_hash_name(value, format)
                    assert result == correct, f"name={value!r}, format={format!r}:"

    def test_lookup_hash_ctor(self):
        """lookup_hash() -- constructor"""
        from passlib.crypto.digest import lookup_hash

        # invalid/unknown names should be rejected
        with pytest.raises(ValueError):
            lookup_hash("new")
        with pytest.raises(ValueError):
            lookup_hash("__name__")
        with pytest.raises(ValueError):
            lookup_hash("sha4")

        # 1. should return hashlib builtin if found
        assert lookup_hash("md5") == (hashlib.md5, 16, 64)

        # 2. should return wrapper around hashlib.new() if found
        try:
            hashlib.new("sha")
            has_sha = True
        except ValueError:
            has_sha = False
        if has_sha:
            record = lookup_hash("sha")
            const = record[0]
            assert record == (const, 20, 64)
            assert (
                hexlify(const(b"abc").digest())
                == b"0164b8a914cd2a5e74c4f7ff082c4d97f1edf880"
            )

        else:
            with pytest.raises(ValueError):
                lookup_hash("sha")

        # 3. should fall back to builtin md4
        try:
            hashlib.new("md4")
            has_md4 = True
        except ValueError:
            has_md4 = False
        record = lookup_hash("md4")
        const = record[0]
        if not has_md4:
            from passlib.crypto._md4 import md4

            assert const is md4
        assert record == (const, 16, 64)
        assert hexlify(const(b"abc").digest()) == b"a448017aaf21d8525fc10ae87aa6729d"

        # should memoize records
        assert lookup_hash("md5") is lookup_hash("md5")

    def test_lookup_hash_w_unknown_name(self):
        """lookup_hash() -- unknown hash name"""
        from passlib.crypto.digest import lookup_hash

        # unknown names should be rejected by default
        with pytest.raises(UnknownHashError):
            lookup_hash("xxx256")

        # required=False should return stub record instead
        info = lookup_hash("xxx256", required=False)
        assert not info.supported

        with pytest.raises(UnknownHashError, match="unknown hash: 'xxx256'"):
            info.const()
        assert info.name == "xxx256"
        assert info.digest_size is None
        assert info.block_size is None

        # should cache stub records
        info2 = lookup_hash("xxx256", required=False)
        assert info2 is info

    def test_mock_fips_mode(self):
        """
        lookup_hash() -- test set_mock_fips_mode()
        """
        from passlib.crypto.digest import lookup_hash, _set_mock_fips_mode

        # check if md5 is available so we can test mock helper
        if not lookup_hash("md5", required=False).supported:
            raise self.skipTest("md5 not supported")

        # enable monkeypatch to mock up fips mode
        _set_mock_fips_mode()
        self.addCleanup(_set_mock_fips_mode, False)

        err_msg = "'md5' hash disabled for fips"
        with pytest.raises(UnknownHashError, match=err_msg):
            lookup_hash("md5")

        info = lookup_hash("md5", required=False)
        assert re.search(err_msg, info.error_text)
        with pytest.raises(UnknownHashError, match=err_msg):
            info.const()

        # should use hardcoded fallback info
        assert info.digest_size == 16
        assert info.block_size == 64

    def test_lookup_hash_metadata(self):
        """lookup_hash() -- metadata"""

        from passlib.crypto.digest import lookup_hash

        # quick test of metadata using known reference - sha256
        info = lookup_hash("sha256")
        assert info.name == "sha256"
        assert info.iana_name == "sha-256"
        assert info.block_size == 64
        assert info.digest_size == 32
        assert lookup_hash("SHA2-256") is info

        # quick test of metadata using known reference - md5
        info = lookup_hash("md5")
        assert info.name == "md5"
        assert info.iana_name == "md5"
        assert info.block_size == 64
        assert info.digest_size == 16

    def test_lookup_hash_alt_types(self):
        """lookup_hash() -- alternate types"""

        from passlib.crypto.digest import lookup_hash

        info = lookup_hash("sha256")
        assert lookup_hash(info) is info
        assert lookup_hash(info.const) is info

        with pytest.raises(TypeError):
            lookup_hash(123)

    # TODO: write full test of compile_hmac() -- currently relying on pbkdf2_hmac() tests


class Pbkdf1_Test(TestCase):
    """test kdf helpers"""

    descriptionPrefix = "passlib.crypto.digest.pbkdf1"

    pbkdf1_tests = [
        # (password, salt, rounds, keylen, hash, result)
        #
        # from http://www.di-mgt.com.au/cryptoKDFs.html
        #
        (
            b"password",
            hb("78578E5A5D63CB06"),
            1000,
            16,
            "sha1",
            hb("dc19847e05c64d2faf10ebfb4a3d2a20"),
        ),
        #
        # custom
        #
        (b"password", b"salt", 1000, 0, "md5", b""),
        (b"password", b"salt", 1000, 1, "md5", hb("84")),
        (b"password", b"salt", 1000, 8, "md5", hb("8475c6a8531a5d27")),
        (b"password", b"salt", 1000, 16, "md5", hb("8475c6a8531a5d27e386cd496457812c")),
        (
            b"password",
            b"salt",
            1000,
            None,
            "md5",
            hb("8475c6a8531a5d27e386cd496457812c"),
        ),
        (
            b"password",
            b"salt",
            1000,
            None,
            "sha1",
            hb("4a8fd48e426ed081b535be5769892fa396293efb"),
        ),
        (
            b"password",
            b"salt",
            1000,
            None,
            "md4",
            hb("f7f2e91100a8f96190f2dd177cb26453"),
        ),
    ]

    def test_known(self):
        """test reference vectors"""
        from passlib.crypto.digest import pbkdf1

        for secret, salt, rounds, keylen, digest, correct in self.pbkdf1_tests:
            result = pbkdf1(digest, secret, salt, rounds, keylen)
            assert result == correct

    def test_border(self):
        """test border cases"""
        from passlib.crypto.digest import pbkdf1

        def helper(secret=b"secret", salt=b"salt", rounds=1, keylen=1, hash="md5"):
            return pbkdf1(hash, secret, salt, rounds, keylen)

        helper()

        # salt/secret wrong type
        with pytest.raises(TypeError):
            helper(secret=1)
        with pytest.raises(TypeError):
            helper(salt=1)

        # non-existent hashes
        with pytest.raises(ValueError):
            helper(hash="missing")

        # rounds < 1 and wrong type
        with pytest.raises(ValueError):
            helper(rounds=0)
        with pytest.raises(TypeError):
            helper(rounds="1")

        # keylen < 0, keylen > block_size, and wrong type
        with pytest.raises(ValueError):
            helper(keylen=-1)
        with pytest.raises(ValueError):
            helper(keylen=17, hash="md5")
        with pytest.raises(TypeError):
            helper(keylen="1")


# NOTE: relying on tox to verify this works under all the various backends.
class Pbkdf2Test(TestCase):
    """test pbkdf2() support"""

    descriptionPrefix = "passlib.crypto.digest.pbkdf2_hmac() <backends: {}>".format(
        ", ".join(PBKDF2_BACKENDS)
    )

    pbkdf2_test_vectors = [
        # (result, secret, salt, rounds, keylen, digest="sha1")
        #
        # from rfc 3962
        #
        # test case 1 / 128 bit
        (
            hb("cdedb5281bb2f801565a1122b2563515"),
            b"password",
            b"ATHENA.MIT.EDUraeburn",
            1,
            16,
        ),
        # test case 2 / 128 bit
        (
            hb("01dbee7f4a9e243e988b62c73cda935d"),
            b"password",
            b"ATHENA.MIT.EDUraeburn",
            2,
            16,
        ),
        # test case 2 / 256 bit
        (
            hb("01dbee7f4a9e243e988b62c73cda935da05378b93244ec8f48a99e61ad799d86"),
            b"password",
            b"ATHENA.MIT.EDUraeburn",
            2,
            32,
        ),
        # test case 3 / 256 bit
        (
            hb("5c08eb61fdf71e4e4ec3cf6ba1f5512ba7e52ddbc5e5142f708a31e2e62b1e13"),
            b"password",
            b"ATHENA.MIT.EDUraeburn",
            1200,
            32,
        ),
        # test case 4 / 256 bit
        (
            hb("d1daa78615f287e6a1c8b120d7062a493f98d203e6be49a6adf4fa574b6e64ee"),
            b"password",
            b"\x12\x34\x56\x78\x78\x56\x34\x12",
            5,
            32,
        ),
        # test case 5 / 256 bit
        (
            hb("139c30c0966bc32ba55fdbf212530ac9c5ec59f1a452f5cc9ad940fea0598ed1"),
            b"X" * 64,
            b"pass phrase equals block size",
            1200,
            32,
        ),
        # test case 6 / 256 bit
        (
            hb("9ccad6d468770cd51b10e6a68721be611a8b4d282601db3b36be9246915ec82a"),
            b"X" * 65,
            b"pass phrase exceeds block size",
            1200,
            32,
        ),
        #
        # from rfc 6070
        #
        (
            hb("0c60c80f961f0e71f3a9b524af6012062fe037a6"),
            b"password",
            b"salt",
            1,
            20,
        ),
        (
            hb("ea6c014dc72d6f8ccd1ed92ace1d41f0d8de8957"),
            b"password",
            b"salt",
            2,
            20,
        ),
        (
            hb("4b007901b765489abead49d926f721d065a429c1"),
            b"password",
            b"salt",
            4096,
            20,
        ),
        # just runs too long - could enable if ALL option is set
        ##(
        ##
        ##    hb("eefe3d61cd4da4e4e9945b3d6ba2158c2634e984"),
        ##    "password", "salt", 16777216, 20,
        ##),
        (
            hb("3d2eec4fe41c849b80c8d83662c0e44a8b291a964cf2f07038"),
            b"passwordPASSWORDpassword",
            b"saltSALTsaltSALTsaltSALTsaltSALTsalt",
            4096,
            25,
        ),
        (
            hb("56fa6aa75548099dcc37d7f03425e0c3"),
            b"pass\00word",
            b"sa\00lt",
            4096,
            16,
        ),
        #
        # from example in http://grub.enbug.org/Authentication
        #
        (
            hb(
                "887CFF169EA8335235D8004242AA7D6187A41E3187DF0CE14E256D85ED"
                "97A97357AAA8FF0A3871AB9EEFF458392F462F495487387F685B7472FC"
                "6C29E293F0A0"
            ),
            b"hello",
            hb(
                "9290F727ED06C38BA4549EF7DE25CF5642659211B7FC076F2D28FEFD71"
                "784BB8D8F6FB244A8CC5C06240631B97008565A120764C0EE9C2CB0073"
                "994D79080136"
            ),
            10000,
            64,
            "sha512",
        ),
        #
        # test vectors from fastpbkdf2 <https://github.com/ctz/fastpbkdf2/blob/master/testdata.py>
        #
        (
            hb(
                "55ac046e56e3089fec1691c22544b605f94185216dde0465e68b9d57c20dacbc"
                "49ca9cccf179b645991664b39d77ef317c71b845b1e30bd509112041d3a19783"
            ),
            b"passwd",
            b"salt",
            1,
            64,
            "sha256",
        ),
        (
            hb(
                "4ddcd8f60b98be21830cee5ef22701f9641a4418d04c0414aeff08876b34ab56"
                "a1d425a1225833549adb841b51c9b3176a272bdebba1d078478f62b397f33c8d"
            ),
            b"Password",
            b"NaCl",
            80000,
            64,
            "sha256",
        ),
        (
            hb("120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b"),
            b"password",
            b"salt",
            1,
            32,
            "sha256",
        ),
        (
            hb("ae4d0c95af6b46d32d0adff928f06dd02a303f8ef3c251dfd6e2d85a95474c43"),
            b"password",
            b"salt",
            2,
            32,
            "sha256",
        ),
        (
            hb("c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a"),
            b"password",
            b"salt",
            4096,
            32,
            "sha256",
        ),
        (
            hb(
                "348c89dbcbd32b2f32d814b8116e84cf2b17347ebc1800181c4e2a1fb8dd53e1c"
                "635518c7dac47e9"
            ),
            b"passwordPASSWORDpassword",
            b"saltSALTsaltSALTsaltSALTsaltSALTsalt",
            4096,
            40,
            "sha256",
        ),
        (
            hb("9e83f279c040f2a11aa4a02b24c418f2d3cb39560c9627fa4f47e3bcc2897c3d"),
            b"",
            b"salt",
            1024,
            32,
            "sha256",
        ),
        (
            hb("ea5808411eb0c7e830deab55096cee582761e22a9bc034e3ece925225b07bf46"),
            b"password",
            b"",
            1024,
            32,
            "sha256",
        ),
        (
            hb("89b69d0516f829893c696226650a8687"),
            b"pass\x00word",
            b"sa\x00lt",
            4096,
            16,
            "sha256",
        ),
        (
            hb("867f70cf1ade02cff3752599a3a53dc4af34c7a669815ae5d513554e1c8cf252"),
            b"password",
            b"salt",
            1,
            32,
            "sha512",
        ),
        (
            hb("e1d9c16aa681708a45f5c7c4e215ceb66e011a2e9f0040713f18aefdb866d53c"),
            b"password",
            b"salt",
            2,
            32,
            "sha512",
        ),
        (
            hb("d197b1b33db0143e018b12f3d1d1479e6cdebdcc97c5c0f87f6902e072f457b5"),
            b"password",
            b"salt",
            4096,
            32,
            "sha512",
        ),
        (
            hb(
                "6e23f27638084b0f7ea1734e0d9841f55dd29ea60a834466f3396bac801fac1eeb"
                "63802f03a0b4acd7603e3699c8b74437be83ff01ad7f55dac1ef60f4d56480c35e"
                "e68fd52c6936"
            ),
            b"passwordPASSWORDpassword",
            b"saltSALTsaltSALTsaltSALTsaltSALTsalt",
            1,
            72,
            "sha512",
        ),
        (
            hb("0c60c80f961f0e71f3a9b524af6012062fe037a6"),
            b"password",
            b"salt",
            1,
            20,
            "sha1",
        ),
        #
        # custom tests
        #
        (
            hb("e248fb6b13365146f8ac6307cc222812"),
            b"secret",
            b"salt",
            10,
            16,
            "sha1",
        ),
        (
            hb("e248fb6b13365146f8ac6307cc2228127872da6d"),
            b"secret",
            b"salt",
            10,
            None,
            "sha1",
        ),
        (
            hb(
                "b1d5485772e6f76d5ebdc11b38d3eff0a5b2bd50dc11f937e86ecacd0cd40d1b"
                "9113e0734e3b76a3"
            ),
            b"secret",
            b"salt",
            62,
            40,
            "md5",
        ),
        (
            hb(
                "ea014cc01f78d3883cac364bb5d054e2be238fb0b6081795a9d84512126e3129"
                "062104d2183464c4"
            ),
            b"secret",
            b"salt",
            62,
            40,
            "md4",
        ),
    ]

    def test_known(self):
        """test reference vectors"""
        for row in self.pbkdf2_test_vectors:
            correct, secret, salt, rounds, keylen = row[:5]
            digest = row[5] if len(row) == 6 else "sha1"
            result = pbkdf2_hmac(digest, secret, salt, rounds, keylen)
            assert result == correct

    def test_backends(self):
        """verify expected backends are present"""
        from passlib.crypto.digest import PBKDF2_BACKENDS

        has_fastpbkdf2 = find_spec("fastpbkdf2") is not None
        assert ("fastpbkdf2" in PBKDF2_BACKENDS) == has_fastpbkdf2

        # check for hashlib
        try:
            from hashlib import pbkdf2_hmac

            has_hashlib_ssl = pbkdf2_hmac.__module__ != "hashlib"
        except ImportError:
            has_hashlib_ssl = False
        assert ("hashlib-ssl" in PBKDF2_BACKENDS) == has_hashlib_ssl

        # check for appropriate builtin
        assert "builtin-from-bytes" not in PBKDF2_BACKENDS

    def test_border(self):
        """test border cases"""

        def helper(
            secret=b"password", salt=b"salt", rounds=1, keylen=None, digest="sha1"
        ):
            return pbkdf2_hmac(digest, secret, salt, rounds, keylen)

        helper()

        # invalid rounds
        with pytest.raises(ValueError):
            helper(rounds=-1)
        with pytest.raises(ValueError):
            helper(rounds=0)
        with pytest.raises(TypeError):
            helper(rounds="x")

        # invalid keylen
        helper(keylen=1)
        with pytest.raises(ValueError):
            helper(keylen=-1)
        with pytest.raises(ValueError):
            helper(keylen=0)
        # NOTE: hashlib actually throws error for keylen>=MAX_SINT32,
        #       but pbkdf2 forbids anything > MAX_UINT32 * digest_size
        with pytest.raises(OverflowError):
            helper(keylen=20 * (2**32 - 1) + 1)
        with pytest.raises(TypeError):
            helper(keylen="x")

        # invalid secret/salt type
        with pytest.raises(TypeError):
            helper(salt=5)
        with pytest.raises(TypeError):
            helper(secret=5)

        # invalid hash
        with pytest.raises(ValueError):
            helper(digest="foo")
        with pytest.raises(TypeError):
            helper(digest=5)

    def test_default_keylen(self):
        """test keylen==None"""

        def helper(
            secret=b"password", salt=b"salt", rounds=1, keylen=None, digest="sha1"
        ):
            return pbkdf2_hmac(digest, secret, salt, rounds, keylen)

        assert len(helper(digest="sha1")) == 20
        assert len(helper(digest="sha256")) == 32
