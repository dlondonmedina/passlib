"""passlib.tests.test_handlers_argon2 - tests for passlib hash algorithms"""

# =============================================================================
# imports
# =============================================================================
# core
import logging

log = logging.getLogger(__name__)
import re
import warnings

# site
# pkg
from passlib import hash
from passlib.tests.utils import HandlerCase, TEST_MODE
from passlib.tests.test_handlers import UPASS_TABLE, PASS_TABLE_UTF8
# module


# =============================================================================
# a bunch of tests lifted nearlky verbatim from official argon2 UTs...
# https://github.com/P-H-C/phc-winner-argon2/blob/master/src/test.c
# =============================================================================
def hashtest(version, t, logM, p, secret, salt, hex_digest, hash):
    return dict(
        version=version,
        rounds=t,
        logM=logM,
        memory_cost=1 << logM,
        parallelism=p,
        secret=secret,
        salt=salt,
        hex_digest=hex_digest,
        hash=hash,
    )


# version 1.3 "I" tests
version = 0x10
reference_data = [
    hashtest(
        version,
        2,
        16,
        1,
        "password",
        "somesalt",
        "f6c4db4a54e2a370627aff3db6176b94a2a209a62c8e36152711802f7b30c694",
        "$argon2i$m=65536,t=2,p=1$c29tZXNhbHQ"
        "$9sTbSlTio3Biev89thdrlKKiCaYsjjYVJxGAL3swxpQ",
    ),
    hashtest(
        version,
        2,
        20,
        1,
        "password",
        "somesalt",
        "9690ec55d28d3ed32562f2e73ea62b02b018757643a2ae6e79528459de8106e9",
        "$argon2i$m=1048576,t=2,p=1$c29tZXNhbHQ"
        "$lpDsVdKNPtMlYvLnPqYrArAYdXZDoq5ueVKEWd6BBuk",
    ),
    hashtest(
        version,
        2,
        18,
        1,
        "password",
        "somesalt",
        "3e689aaa3d28a77cf2bc72a51ac53166761751182f1ee292e3f677a7da4c2467",
        "$argon2i$m=262144,t=2,p=1$c29tZXNhbHQ"
        "$Pmiaqj0op3zyvHKlGsUxZnYXURgvHuKS4/Z3p9pMJGc",
    ),
    hashtest(
        version,
        2,
        8,
        1,
        "password",
        "somesalt",
        "fd4dd83d762c49bdeaf57c47bdcd0c2f1babf863fdeb490df63ede9975fccf06",
        "$argon2i$m=256,t=2,p=1$c29tZXNhbHQ"
        "$/U3YPXYsSb3q9XxHvc0MLxur+GP960kN9j7emXX8zwY",
    ),
    hashtest(
        version,
        2,
        8,
        2,
        "password",
        "somesalt",
        "b6c11560a6a9d61eac706b79a2f97d68b4463aa3ad87e00c07e2b01e90c564fb",
        "$argon2i$m=256,t=2,p=2$c29tZXNhbHQ"
        "$tsEVYKap1h6scGt5ovl9aLRGOqOth+AMB+KwHpDFZPs",
    ),
    hashtest(
        version,
        1,
        16,
        1,
        "password",
        "somesalt",
        "81630552b8f3b1f48cdb1992c4c678643d490b2b5eb4ff6c4b3438b5621724b2",
        "$argon2i$m=65536,t=1,p=1$c29tZXNhbHQ"
        "$gWMFUrjzsfSM2xmSxMZ4ZD1JCytetP9sSzQ4tWIXJLI",
    ),
    hashtest(
        version,
        4,
        16,
        1,
        "password",
        "somesalt",
        "f212f01615e6eb5d74734dc3ef40ade2d51d052468d8c69440a3a1f2c1c2847b",
        "$argon2i$m=65536,t=4,p=1$c29tZXNhbHQ"
        "$8hLwFhXm6110c03D70Ct4tUdBSRo2MaUQKOh8sHChHs",
    ),
    hashtest(
        version,
        2,
        16,
        1,
        "differentpassword",
        "somesalt",
        "e9c902074b6754531a3a0be519e5baf404b30ce69b3f01ac3bf21229960109a3",
        "$argon2i$m=65536,t=2,p=1$c29tZXNhbHQ"
        "$6ckCB0tnVFMaOgvlGeW69ASzDOabPwGsO/ISKZYBCaM",
    ),
    hashtest(
        version,
        2,
        16,
        1,
        "password",
        "diffsalt",
        "79a103b90fe8aef8570cb31fc8b22259778916f8336b7bdac3892569d4f1c497",
        "$argon2i$m=65536,t=2,p=1$ZGlmZnNhbHQ"
        "$eaEDuQ/orvhXDLMfyLIiWXeJFvgza3vaw4kladTxxJc",
    ),
]

# version 1.9 "I" tests
version = 0x13
reference_data.extend(
    [
        hashtest(
            version,
            2,
            16,
            1,
            "password",
            "somesalt",
            "c1628832147d9720c5bd1cfd61367078729f6dfb6f8fea9ff98158e0d7816ed0",
            "$argon2i$v=19$m=65536,t=2,p=1$c29tZXNhbHQ"
            "$wWKIMhR9lyDFvRz9YTZweHKfbftvj+qf+YFY4NeBbtA",
        ),
        hashtest(
            version,
            2,
            20,
            1,
            "password",
            "somesalt",
            "d1587aca0922c3b5d6a83edab31bee3c4ebaef342ed6127a55d19b2351ad1f41",
            "$argon2i$v=19$m=1048576,t=2,p=1$c29tZXNhbHQ"
            "$0Vh6ygkiw7XWqD7asxvuPE667zQu1hJ6VdGbI1GtH0E",
        ),
        hashtest(
            version,
            2,
            18,
            1,
            "password",
            "somesalt",
            "296dbae80b807cdceaad44ae741b506f14db0959267b183b118f9b24229bc7cb",
            "$argon2i$v=19$m=262144,t=2,p=1$c29tZXNhbHQ"
            "$KW266AuAfNzqrUSudBtQbxTbCVkmexg7EY+bJCKbx8s",
        ),
        hashtest(
            version,
            2,
            8,
            1,
            "password",
            "somesalt",
            "89e9029f4637b295beb027056a7336c414fadd43f6b208645281cb214a56452f",
            "$argon2i$v=19$m=256,t=2,p=1$c29tZXNhbHQ"
            "$iekCn0Y3spW+sCcFanM2xBT63UP2sghkUoHLIUpWRS8",
        ),
        hashtest(
            version,
            2,
            8,
            2,
            "password",
            "somesalt",
            "4ff5ce2769a1d7f4c8a491df09d41a9fbe90e5eb02155a13e4c01e20cd4eab61",
            "$argon2i$v=19$m=256,t=2,p=2$c29tZXNhbHQ"
            "$T/XOJ2mh1/TIpJHfCdQan76Q5esCFVoT5MAeIM1Oq2E",
        ),
        hashtest(
            version,
            1,
            16,
            1,
            "password",
            "somesalt",
            "d168075c4d985e13ebeae560cf8b94c3b5d8a16c51916b6f4ac2da3ac11bbecf",
            "$argon2i$v=19$m=65536,t=1,p=1$c29tZXNhbHQ"
            "$0WgHXE2YXhPr6uVgz4uUw7XYoWxRkWtvSsLaOsEbvs8",
        ),
        hashtest(
            version,
            4,
            16,
            1,
            "password",
            "somesalt",
            "aaa953d58af3706ce3df1aefd4a64a84e31d7f54175231f1285259f88174ce5b",
            "$argon2i$v=19$m=65536,t=4,p=1$c29tZXNhbHQ"
            "$qqlT1YrzcGzj3xrv1KZKhOMdf1QXUjHxKFJZ+IF0zls",
        ),
        hashtest(
            version,
            2,
            16,
            1,
            "differentpassword",
            "somesalt",
            "14ae8da01afea8700c2358dcef7c5358d9021282bd88663a4562f59fb74d22ee",
            "$argon2i$v=19$m=65536,t=2,p=1$c29tZXNhbHQ"
            "$FK6NoBr+qHAMI1jc73xTWNkCEoK9iGY6RWL1n7dNIu4",
        ),
        hashtest(
            version,
            2,
            16,
            1,
            "password",
            "diffsalt",
            "b0357cccfbef91f3860b0dba447b2348cbefecadaf990abfe9cc40726c521271",
            "$argon2i$v=19$m=65536,t=2,p=1$ZGlmZnNhbHQ"
            "$sDV8zPvvkfOGCw26RHsjSMvv7K2vmQq/6cxAcmxSEnE",
        ),
    ]
)

# version 1.9 "ID" tests
version = 0x13
reference_data.extend(
    [
        hashtest(
            version,
            2,
            16,
            1,
            "password",
            "somesalt",
            "09316115d5cf24ed5a15a31a3ba326e5cf32edc24702987c02b6566f61913cf7",
            "$argon2id$v=19$m=65536,t=2,p=1$c29tZXNhbHQ"
            "$CTFhFdXPJO1aFaMaO6Mm5c8y7cJHAph8ArZWb2GRPPc",
        ),
        hashtest(
            version,
            2,
            18,
            1,
            "password",
            "somesalt",
            "78fe1ec91fb3aa5657d72e710854e4c3d9b9198c742f9616c2f085bed95b2e8c",
            "$argon2id$v=19$m=262144,t=2,p=1$c29tZXNhbHQ"
            "$eP4eyR+zqlZX1y5xCFTkw9m5GYx0L5YWwvCFvtlbLow",
        ),
        hashtest(
            version,
            2,
            8,
            1,
            "password",
            "somesalt",
            "9dfeb910e80bad0311fee20f9c0e2b12c17987b4cac90c2ef54d5b3021c68bfe",
            "$argon2id$v=19$m=256,t=2,p=1$c29tZXNhbHQ"
            "$nf65EOgLrQMR/uIPnA4rEsF5h7TKyQwu9U1bMCHGi/4",
        ),
        hashtest(
            version,
            2,
            8,
            2,
            "password",
            "somesalt",
            "6d093c501fd5999645e0ea3bf620d7b8be7fd2db59c20d9fff9539da2bf57037",
            "$argon2id$v=19$m=256,t=2,p=2$c29tZXNhbHQ"
            "$bQk8UB/VmZZF4Oo79iDXuL5/0ttZwg2f/5U52iv1cDc",
        ),
        hashtest(
            version,
            1,
            16,
            1,
            "password",
            "somesalt",
            "f6a5adc1ba723dddef9b5ac1d464e180fcd9dffc9d1cbf76cca2fed795d9ca98",
            "$argon2id$v=19$m=65536,t=1,p=1$c29tZXNhbHQ"
            "$9qWtwbpyPd3vm1rB1GThgPzZ3/ydHL92zKL+15XZypg",
        ),
        hashtest(
            version,
            4,
            16,
            1,
            "password",
            "somesalt",
            "9025d48e68ef7395cca9079da4c4ec3affb3c8911fe4f86d1a2520856f63172c",
            "$argon2id$v=19$m=65536,t=4,p=1$c29tZXNhbHQ"
            "$kCXUjmjvc5XMqQedpMTsOv+zyJEf5PhtGiUghW9jFyw",
        ),
        hashtest(
            version,
            2,
            16,
            1,
            "differentpassword",
            "somesalt",
            "0b84d652cf6b0c4beaef0dfe278ba6a80df6696281d7e0d2891b817d8c458fde",
            "$argon2id$v=19$m=65536,t=2,p=1$c29tZXNhbHQ"
            "$C4TWUs9rDEvq7w3+J4umqA32aWKB1+DSiRuBfYxFj94",
        ),
        hashtest(
            version,
            2,
            16,
            1,
            "password",
            "diffsalt",
            "bdf32b05ccc42eb15d58fd19b1f856b113da1e9a5874fdcc544308565aa8141c",
            "$argon2id$v=19$m=65536,t=2,p=1$ZGlmZnNhbHQ"
            "$vfMrBczELrFdWP0ZsfhWsRPaHppYdP3MVEMIVlqoFBw",
        ),
    ]
)


# =============================================================================
# argon2
# =============================================================================
class _base_argon2_test(HandlerCase):
    handler = hash.argon2

    known_correct_hashes = [
        #
        # custom
        #
        # sample test
        ("password", "$argon2i$v=19$m=256,t=1,p=1$c29tZXNhbHQ$AJFIsNZTMKTAewB4+ETN1A"),
        # sample w/ all parameters different
        ("password", "$argon2i$v=19$m=380,t=2,p=2$c29tZXNhbHQ$SrssP8n7m/12VWPM8dvNrw"),
        # ensures utf-8 used for unicode
        (
            UPASS_TABLE,
            "$argon2i$v=19$m=512,t=2,p=2$1sV0O4PWLtc12Ypv1f7oGw$"
            "z+yqzlKtrq3SaNfXDfIDnQ",
        ),
        (
            PASS_TABLE_UTF8,
            "$argon2i$v=19$m=512,t=2,p=2$1sV0O4PWLtc12Ypv1f7oGw$"
            "z+yqzlKtrq3SaNfXDfIDnQ",
        ),
        # ensure trailing null bytes handled correctly
        (
            "password\x00",
            "$argon2i$v=19$m=512,t=2,p=2$c29tZXNhbHQ$Fb5+nPuLzZvtqKRwqUEtUQ",
        ),
        # sample with type D (generated via argon_cffi2.PasswordHasher)
        (
            "password",
            "$argon2d$v=19$m=102400,t=2,p=8$g2RodLh8j8WbSdCp+lUy/A$zzAJqL/HSjm809PYQu6qkA",
        ),
    ]

    known_malformed_hashes = [
        # unknown hash type
        "$argon2qq$v=19$t=2,p=4$c29tZXNhbHQAAAAAAAAAAA$QWLzI4TY9HkL2ZTLc8g6SinwdhZewYrzz9zxCo0bkGY",
        # missing 'm' param
        "$argon2i$v=19$t=2,p=4$c29tZXNhbHQAAAAAAAAAAA$QWLzI4TY9HkL2ZTLc8g6SinwdhZewYrzz9zxCo0bkGY",
        # 't' param > max uint32
        "$argon2i$v=19$m=65536,t=8589934592,p=4$c29tZXNhbHQAAAAAAAAAAA$QWLzI4TY9HkL2ZTLc8g6SinwdhZewYrzz9zxCo0bkGY",
        # unexpected param
        "$argon2i$v=19$m=65536,t=2,p=4,q=5$c29tZXNhbHQAAAAAAAAAAA$QWLzI4TY9HkL2ZTLc8g6SinwdhZewYrzz9zxCo0bkGY",
        # wrong param order
        "$argon2i$v=19$t=2,m=65536,p=4,q=5$c29tZXNhbHQAAAAAAAAAAA$QWLzI4TY9HkL2ZTLc8g6SinwdhZewYrzz9zxCo0bkGY",
        # constraint violation: m < 8 * p
        "$argon2i$v=19$m=127,t=2,p=16$c29tZXNhbHQ$IMit9qkFULCMA/ViizL57cnTLOa5DiVM9eMwpAvPwr4",
    ]

    known_parsehash_results = [
        (
            "$argon2i$v=19$m=256,t=2,p=3$c29tZXNhbHQ$AJFIsNZTMKTAewB4+ETN1A",
            dict(
                type="i",
                memory_cost=256,
                rounds=2,
                parallelism=3,
                salt=b"somesalt",
                checksum=b"\x00\x91H\xb0\xd6S0\xa4\xc0{\x00x\xf8D\xcd\xd4",
            ),
        ),
    ]

    def setUpWarnings(self):
        super().setUpWarnings()
        warnings.filterwarnings("ignore", ".*Using argon2pure backend.*")

    def do_stub_encrypt(self, handler=None, **settings):
        if self.backend == "argon2_cffi":
            # overriding default since no way to get stub config from argon2._calc_hash()
            # (otherwise test_21b_max_rounds blocks trying to do max rounds)
            handler = (handler or self.handler).using(**settings)
            self = handler(use_defaults=True)
            self.checksum = self._stub_checksum
            assert self.checksum
            return self.to_string()
        else:
            return super().do_stub_encrypt(handler, **settings)

    def test_03_legacy_hash_workflow(self):
        # override base method
        raise self.skipTest("legacy 1.6 workflow not supported")

    def test_keyid_parameter(self):
        # NOTE: keyid parameter currently not supported by official argon2 hash parser,
        #       even though it's mentioned in the format spec.
        #       we're trying to be consistent w/ this, so hashes w/ keyid should
        #       always through a NotImplementedError.
        self.assertRaises(
            NotImplementedError,
            self.handler.verify,
            "password",
            "$argon2i$v=19$m=65536,t=2,p=4,keyid=ABCD$c29tZXNhbHQ$"
            "IMit9qkFULCMA/ViizL57cnTLOa5DiVM9eMwpAvPwr4",
        )

    def test_data_parameter(self):
        # NOTE: argon2 c library doesn't support passing in a data parameter to argon2_hash();
        #       but argon2_verify() appears to parse that info... but then discards it (!?).
        #       not sure what proper behavior is, filed issue -- https://github.com/P-H-C/phc-winner-argon2/issues/143
        #       For now, replicating behavior we have for the two backends, to detect when things change.
        handler = self.handler

        # ref hash of 'password' when 'data' is correctly passed into argon2()
        sample1 = "$argon2i$v=19$m=512,t=2,p=2,data=c29tZWRhdGE$c29tZXNhbHQ$KgHyCesFyyjkVkihZ5VNFw"

        # ref hash of 'password' when 'data' is silently discarded (same digest as w/o data)
        sample2 = "$argon2i$v=19$m=512,t=2,p=2,data=c29tZWRhdGE$c29tZXNhbHQ$uEeXt1dxN1iFKGhklseW4w"

        # hash of 'password' w/o the data field
        sample3 = "$argon2i$v=19$m=512,t=2,p=2$c29tZXNhbHQ$uEeXt1dxN1iFKGhklseW4w"

        #
        # test sample 1
        #

        if self.backend == "argon2_cffi":
            # argon2_cffi v16.1 would incorrectly return False here.
            # but v16.2 patches so it throws error on data parameter.
            # our code should detect that, and adapt it into a NotImplementedError
            self.assertRaises(NotImplementedError, handler.verify, "password", sample1)

            # incorrectly returns sample3, dropping data parameter
            self.assertEqual(handler.genhash("password", sample1), sample3)

        else:
            assert self.backend == "argon2pure"
            # should parse and verify
            self.assertTrue(handler.verify("password", sample1))

            # should preserve sample1
            self.assertEqual(handler.genhash("password", sample1), sample1)

        #
        # test sample 2
        #

        if self.backend == "argon2_cffi":
            # argon2_cffi v16.1 would incorrectly return True here.
            # but v16.2 patches so it throws error on data parameter.
            # our code should detect that, and adapt it into a NotImplementedError
            self.assertRaises(NotImplementedError, handler.verify, "password", sample2)

            # incorrectly returns sample3, dropping data parameter
            self.assertEqual(handler.genhash("password", sample1), sample3)

        else:
            assert self.backend == "argon2pure"
            # should parse, but fail to verify
            self.assertFalse(self.handler.verify("password", sample2))

            # should return sample1 (corrected digest)
            self.assertEqual(handler.genhash("password", sample2), sample1)

    def test_keyid_and_data_parameters(self):
        # test combination of the two, just in case
        self.assertRaises(
            NotImplementedError,
            self.handler.verify,
            "stub",
            "$argon2i$v=19$m=65536,t=2,p=4,keyid=ABCD,data=EFGH$c29tZXNhbHQ$"
            "IMit9qkFULCMA/ViizL57cnTLOa5DiVM9eMwpAvPwr4",
        )

    def test_type_kwd(self):
        cls = self.handler

        # XXX: this mirrors test_30_HasManyIdents();
        #      maybe switch argon2 class to use that mixin instead of "type" kwd?

        # check settings
        self.assertTrue("type" in cls.setting_kwds)

        # check supported type_values
        for value in cls.type_values:
            self.assertIsInstance(value, str)
        self.assertTrue("i" in cls.type_values)
        self.assertTrue("d" in cls.type_values)

        # check default
        self.assertTrue(cls.type in cls.type_values)

        # check constructor validates ident correctly.
        handler = cls
        hash = self.get_sample_hash()[1]
        kwds = handler.parsehash(hash)
        del kwds["type"]

        # ... accepts good type
        handler(type=cls.type, **kwds)

        # XXX: this is policy "ident" uses, maybe switch to it?
        # # ... requires type w/o defaults
        # self.assertRaises(TypeError, handler, **kwds)
        handler(**kwds)

        # ... supplies default type
        handler(use_defaults=True, **kwds)

        # ... rejects bad type
        self.assertRaises(ValueError, handler, type="xXx", **kwds)

    def test_type_using(self):
        handler = self.handler

        # XXX: this mirrors test_has_many_idents_using();
        #      maybe switch argon2 class to use that mixin instead of "type" kwd?

        orig_type = handler.type
        for alt_type in handler.type_values:
            if alt_type != orig_type:
                break
        else:
            raise AssertionError(
                "expected to find alternate type: default=%r values=%r"
                % (orig_type, handler.type_values)
            )

        def effective_type(cls):
            return cls(use_defaults=True).type

        # keep default if nothing else specified
        subcls = handler.using()
        self.assertEqual(subcls.type, orig_type)

        # accepts alt type
        subcls = handler.using(type=alt_type)
        self.assertEqual(subcls.type, alt_type)
        self.assertEqual(handler.type, orig_type)

        # check subcls actually *generates* default type,
        # and that we didn't affect orig handler
        self.assertEqual(effective_type(subcls), alt_type)
        self.assertEqual(effective_type(handler), orig_type)

        # rejects bad type
        self.assertRaises(ValueError, handler.using, type="xXx")

        # honor 'type' alias
        subcls = handler.using(type=alt_type)
        self.assertEqual(subcls.type, alt_type)
        self.assertEqual(handler.type, orig_type)

        # check type aliases are being honored
        self.assertEqual(effective_type(handler.using(type="I")), "i")

    def test_needs_update_w_type(self):
        handler = self.handler

        hash = handler.hash("stub")
        self.assertFalse(handler.needs_update(hash))

        hash2 = re.sub(r"\$argon2\w+\$", "$argon2d$", hash)
        self.assertTrue(handler.needs_update(hash2))

    def test_needs_update_w_version(self):
        handler = self.handler.using(
            memory_cost=65536, time_cost=2, parallelism=4, digest_size=32
        )
        hash = (
            "$argon2i$m=65536,t=2,p=4$c29tZXNhbHQAAAAAAAAAAA$"
            "QWLzI4TY9HkL2ZTLc8g6SinwdhZewYrzz9zxCo0bkGY"
        )
        if handler.max_version == 0x10:
            self.assertFalse(handler.needs_update(hash))
        else:
            self.assertTrue(handler.needs_update(hash))

    def test_argon_byte_encoding(self):
        """verify we're using right base64 encoding for argon2"""
        handler = self.handler
        if handler.version != 0x13:
            # TODO: make this fatal, and add refs for other version.
            raise self.skipTest("handler uses wrong version for sample hashes")

        # 8 byte salt
        salt = b"somesalt"
        temp = handler.using(
            memory_cost=256,
            time_cost=2,
            parallelism=2,
            salt=salt,
            checksum_size=32,
            type="i",
        )
        hash = temp.hash("password")
        self.assertEqual(
            hash,
            "$argon2i$v=19$m=256,t=2,p=2"
            "$c29tZXNhbHQ"
            "$T/XOJ2mh1/TIpJHfCdQan76Q5esCFVoT5MAeIM1Oq2E",
        )

        # 16 byte salt
        salt = b"somesalt\x00\x00\x00\x00\x00\x00\x00\x00"
        temp = handler.using(
            memory_cost=256,
            time_cost=2,
            parallelism=2,
            salt=salt,
            checksum_size=32,
            type="i",
        )
        hash = temp.hash("password")
        self.assertEqual(
            hash,
            "$argon2i$v=19$m=256,t=2,p=2"
            "$c29tZXNhbHQAAAAAAAAAAA"
            "$rqnbEp1/jFDUEKZZmw+z14amDsFqMDC53dIe57ZHD38",
        )

    class FuzzHashGenerator(HandlerCase.FuzzHashGenerator):
        settings_map = HandlerCase.FuzzHashGenerator.settings_map.copy()
        settings_map.update(memory_cost="random_memory_cost", type="random_type")

        def random_type(self):
            return self.rng.choice(self.handler.type_values)

        def random_memory_cost(self):
            if self.test.backend == "argon2pure":
                return self.randintgauss(128, 384, 256, 128)
            else:
                return self.randintgauss(128, 32767, 16384, 4096)

        # TODO: fuzz parallelism, digest_size


# -----------------------------------------
# test suites for specific backends
# -----------------------------------------


class argon2_argon2_cffi_test(_base_argon2_test.create_backend_case("argon2_cffi")):
    # add some more test vectors that take too long under argon2pure
    known_correct_hashes = _base_argon2_test.known_correct_hashes + [
        #
        # sample hashes from argon2 cffi package's unittests,
        # which in turn were generated by official argon2 cmdline tool.
        #
        # v1.2, type I, w/o a version tag
        (
            "password",
            "$argon2i$m=65536,t=2,p=4$c29tZXNhbHQAAAAAAAAAAA$"
            "QWLzI4TY9HkL2ZTLc8g6SinwdhZewYrzz9zxCo0bkGY",
        ),
        # v1.3, type I
        (
            "password",
            "$argon2i$v=19$m=65536,t=2,p=4$c29tZXNhbHQ$"
            "IMit9qkFULCMA/ViizL57cnTLOa5DiVM9eMwpAvPwr4",
        ),
        # v1.3, type D
        (
            "password",
            "$argon2d$v=19$m=65536,t=2,p=4$c29tZXNhbHQ$"
            "cZn5d+rFh+ZfuRhm2iGUGgcrW5YLeM6q7L3vBsdmFA0",
        ),
        # v1.3, type ID
        (
            "password",
            "$argon2id$v=19$m=65536,t=2,p=4$c29tZXNhbHQ$"
            "GpZ3sK/oH9p7VIiV56G/64Zo/8GaUw434IimaPqxwCo",
        ),
        #
        # custom
        #
        # ensure trailing null bytes handled correctly
        (
            "password\x00",
            "$argon2i$v=19$m=65536,t=2,p=4$c29tZXNhbHQ$"
            "Vpzuc0v0SrP88LcVvmg+z5RoOYpMDKH/lt6O+CZabIQ",
        ),
    ]

    # add reference hashes from argon2 clib tests
    known_correct_hashes.extend(
        (info["secret"], info["hash"])
        for info in reference_data
        if info["logM"] <= (18 if TEST_MODE("full") else 16)
    )


class argon2_argon2pure_test(_base_argon2_test.create_backend_case("argon2pure")):
    # XXX: setting max_threads at 1 to prevent argon2pure from using multiprocessing,
    #      which causes big problems when testing under pypy.
    #      would like a "pure_use_threads" option instead, to make it use multiprocessing.dummy instead.
    handler = hash.argon2.using(memory_cost=32, parallelism=2)

    # don't use multiprocessing for unittests, makes it a lot harder to ctrl-c
    # XXX: make this controlled by env var?
    handler.pure_use_threads = True

    # add reference hashes from argon2 clib tests
    known_correct_hashes = _base_argon2_test.known_correct_hashes[:]

    known_correct_hashes.extend(
        (info["secret"], info["hash"]) for info in reference_data if info["logM"] < 16
    )

    class FuzzHashGenerator(_base_argon2_test.FuzzHashGenerator):
        def random_rounds(self):
            # decrease default rounds for fuzz testing to speed up volume.
            return self.randintgauss(1, 3, 2, 1)


# =============================================================================
# eof
# =============================================================================
