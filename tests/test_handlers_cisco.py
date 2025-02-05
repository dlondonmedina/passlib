import pytest

from passlib import hash, exc
from .utils import UserHandlerMixin, HandlerCase, repeat_string
from .test_handlers import UPASS_TABLE

# module
__all__ = [
    "cisco_pix_test",
    "cisco_asa_test",
    "cisco_type7_test",
]


class _PixAsaSharedTest(UserHandlerMixin, HandlerCase):
    """
    class w/ shared info for PIX & ASA tests.
    """

    __unittest_skip = True  # for TestCase
    requires_user = False  # for UserHandlerMixin

    #: shared list of hashes which should be identical under pix & asa7
    #: (i.e. combined secret + user < 17 bytes)
    pix_asa_shared_hashes = [
        #
        # http://www.perlmonks.org/index.pl?node_id=797623
        #
        (("cisco", ""), "2KFQnbNIdI.2KYOU"),  # confirmed ASA 9.6
        #
        # http://www.hsc.fr/ressources/breves/pix_crack.html.en
        #
        (("hsc", ""), "YtT8/k6Np8F1yz2c"),  # confirmed ASA 9.6
        #
        # www.freerainbowtables.com/phpBB3/viewtopic.php?f=2&t=1441
        #
        (("", ""), "8Ry2YjIyt7RRXU24"),  # confirmed ASA 9.6
        (("cisco", "john"), "hN7LzeyYjw12FSIU"),
        (("cisco", "jack"), "7DrfeZ7cyOj/PslD"),
        #
        # http://comments.gmane.org/gmane.comp.security.openwall.john.user/2529
        #
        (("ripper", "alex"), "h3mJrcH0901pqX/m"),
        (("cisco", "cisco"), "3USUcOPFUiMCO4Jk"),
        (("cisco", "cisco1"), "3USUcOPFUiMCO4Jk"),
        (("CscFw-ITC!", "admcom"), "lZt7HSIXw3.QP7.R"),
        ("cangetin", "TynyB./ftknE77QP"),
        (("cangetin", "rramsey"), "jgBZqYtsWfGcUKDi"),
        #
        # http://openwall.info/wiki/john/sample-hashes
        #
        (("phonehome", "rharris"), "zyIIMSYjiPm0L7a6"),
        #
        # http://www.openwall.com/lists/john-users/2010/08/08/3
        #
        (("cangetin", ""), "TynyB./ftknE77QP"),
        (("cangetin", "rramsey"), "jgBZqYtsWfGcUKDi"),
        #
        # from JTR 1.7.9
        #
        ("test1", "TRPEas6f/aa6JSPL"),
        ("test2", "OMT6mXmAvGyzrCtp"),
        ("test3", "gTC7RIy1XJzagmLm"),
        ("test4", "oWC1WRwqlBlbpf/O"),
        ("password", "NuLKvvWGg.x9HEKO"),
        ("0123456789abcdef", ".7nfVBEIEu4KbF/1"),
        #
        # http://www.cisco.com/en/US/docs/security/pix/pix50/configuration/guide/commands.html#wp5472
        #
        (("1234567890123456", ""), "feCkwUGktTCAgIbD"),  # canonical source
        (("watag00s1am", ""), "jMorNbK0514fadBh"),  # canonical source
        #
        # custom
        #
        (("cisco1", "cisco1"), "jmINXNH6p1BxUppp"),
        # ensures utf-8 used for unicode
        (UPASS_TABLE, "CaiIvkLMu2TOHXGT"),
        #
        # passlib reference vectors
        #
        # Some of these have been confirmed on various ASA firewalls,
        # and the exact version is noted next to each hash.
        # Would like to verify these under more PIX & ASA versions.
        #
        # Those without a note are generally an extrapolation,
        # to ensure the code stays consistent, but for various reasons,
        # hasn't been verified.
        #
        # * One such case is usernames w/ 1 & 2 digits --
        #   ASA (9.6 at least) requires 3+ digits in username.
        #
        # The following hashes (below 13 chars) should be identical for PIX/ASA.
        # Ones which differ are listed separately in the known_correct_hashes
        # list for the two test classes.
        #
        # 4 char password
        (("1234", ""), "RLPMUQ26KL4blgFN"),  # confirmed ASA 9.6
        # 8 char password
        (("01234567", ""), "0T52THgnYdV1tlOF"),  # confirmed ASA 9.6
        (("01234567", "3"), ".z0dT9Alkdc7EIGS"),
        (("01234567", "36"), "CC3Lam53t/mHhoE7"),
        (("01234567", "365"), "8xPrWpNnBdD2DzdZ"),  # confirmed ASA 9.6
        (("01234567", "3333"), ".z0dT9Alkdc7EIGS"),  # confirmed ASA 9.6
        (("01234567", "3636"), "CC3Lam53t/mHhoE7"),  # confirmed ASA 9.6
        (("01234567", "3653"), "8xPrWpNnBdD2DzdZ"),  # confirmed ASA 9.6
        (("01234567", "adm"), "dfWs2qiao6KD/P2L"),  # confirmed ASA 9.6
        (("01234567", "adma"), "dfWs2qiao6KD/P2L"),  # confirmed ASA 9.6
        (("01234567", "admad"), "dfWs2qiao6KD/P2L"),  # confirmed ASA 9.6
        (("01234567", "user"), "PNZ4ycbbZ0jp1.j1"),  # confirmed ASA 9.6
        (("01234567", "user1234"), "PNZ4ycbbZ0jp1.j1"),  # confirmed ASA 9.6
        # 12 char password
        (("0123456789ab", ""), "S31BxZOGlAigndcJ"),  # confirmed ASA 9.6
        (("0123456789ab", "36"), "wFqSX91X5.YaRKsi"),
        (("0123456789ab", "365"), "qjgo3kNgTVxExbno"),  # confirmed ASA 9.6
        (("0123456789ab", "3333"), "mcXPL/vIZcIxLUQs"),  # confirmed ASA 9.6
        (("0123456789ab", "3636"), "wFqSX91X5.YaRKsi"),  # confirmed ASA 9.6
        (("0123456789ab", "3653"), "qjgo3kNgTVxExbno"),  # confirmed ASA 9.6
        (("0123456789ab", "user"), "f.T4BKdzdNkjxQl7"),  # confirmed ASA 9.6
        (("0123456789ab", "user1234"), "f.T4BKdzdNkjxQl7"),  # confirmed ASA 9.6
        # NOTE: remaining reference vectors for 13+ char passwords
        # are split up between cisco_pix & cisco_asa tests.
        # unicode passwords
        # ASA supposedly uses utf-8 encoding, but entering non-ascii
        # chars is error-prone, and while UTF-8 appears to be intended,
        # observed behaviors include:
        # * ssh cli stripping non-ascii chars entirely
        # * ASDM web iface double-encoding utf-8 strings
        (("t\xe1ble".encode(), "user"), "Og8fB4NyF0m5Ed9c"),
        (
            ("t\xe1ble".encode().decode("latin-1").encode("utf-8"), "user"),
            "cMvFC2XVBmK/68yB",
        ),  # confirmed ASA 9.6 when typed into ASDM
    ]

    def test_calc_digest_spoiler(self):
        """
        _calc_checksum() -- spoil oversize passwords during verify

        for details, see 'spoil_digest' flag instead that function.
        this helps cisco_pix/cisco_asa implement their policy of
        ``.truncate_verify_reject=True``.
        """

        def calc(secret, for_hash=False):
            return self.handler(use_defaults=for_hash)._calc_checksum(secret)

        # short (non-truncated) password
        short_secret = repeat_string("1234", self.handler.truncate_size)
        short_hash = calc(short_secret)

        # longer password should have totally different hash,
        # to prevent verify from matching (i.e. "spoiled").
        long_secret = short_secret + "X"
        long_hash = calc(long_secret)
        assert long_hash != short_hash

        # spoiled hash should depend on whole secret,
        # so that output isn't predictable
        alt_long_secret = short_secret + "Y"
        alt_long_hash = calc(alt_long_secret)
        assert alt_long_hash != short_hash
        assert alt_long_hash != long_hash

        # for hash(), should throw error if password too large
        calc(short_secret, for_hash=True)
        with pytest.raises(exc.PasswordSizeError):
            calc(long_secret, for_hash=True)
        with pytest.raises(exc.PasswordSizeError):
            calc(alt_long_secret, for_hash=True)


class cisco_pix_test(_PixAsaSharedTest):
    handler = hash.cisco_pix

    #: known correct pix hashes
    known_correct_hashes = _PixAsaSharedTest.pix_asa_shared_hashes + [
        #
        # passlib reference vectors (PIX-specific)
        #
        # NOTE: See 'pix_asa_shared_hashes' for general PIX+ASA vectors,
        #       and general notes about the 'passlib reference vectors' test set.
        #
        #       All of the following are PIX-specific, as ASA starts
        #       to use a different padding size at 13 characters.
        #
        # TODO: these need confirming w/ an actual PIX system.
        #
        # 13 char password
        (("0123456789abc", ""), "eacOpB7vE7ZDukSF"),
        (("0123456789abc", "3"), "ylJTd/qei66WZe3w"),
        (("0123456789abc", "36"), "hDx8QRlUhwd6bU8N"),
        (("0123456789abc", "365"), "vYOOtnkh1HXcMrM7"),
        (("0123456789abc", "3333"), "ylJTd/qei66WZe3w"),
        (("0123456789abc", "3636"), "hDx8QRlUhwd6bU8N"),
        (("0123456789abc", "3653"), "vYOOtnkh1HXcMrM7"),
        (("0123456789abc", "user"), "f4/.SALxqDo59mfV"),
        (("0123456789abc", "user1234"), "f4/.SALxqDo59mfV"),
        # 14 char password
        (("0123456789abcd", ""), "6r8888iMxEoPdLp4"),
        (("0123456789abcd", "3"), "f5lvmqWYj9gJqkIH"),
        (("0123456789abcd", "36"), "OJJ1Khg5HeAYBH1c"),
        (("0123456789abcd", "365"), "OJJ1Khg5HeAYBH1c"),
        (("0123456789abcd", "3333"), "f5lvmqWYj9gJqkIH"),
        (("0123456789abcd", "3636"), "OJJ1Khg5HeAYBH1c"),
        (("0123456789abcd", "3653"), "OJJ1Khg5HeAYBH1c"),
        (("0123456789abcd", "adm"), "DbPLCFIkHc2SiyDk"),
        (("0123456789abcd", "adma"), "DbPLCFIkHc2SiyDk"),
        (("0123456789abcd", "user"), "WfO2UiTapPkF/FSn"),
        (("0123456789abcd", "user1234"), "WfO2UiTapPkF/FSn"),
        # 15 char password
        (("0123456789abcde", ""), "al1e0XFIugTYLai3"),
        (("0123456789abcde", "3"), "lYbwBu.f82OIApQB"),
        (("0123456789abcde", "36"), "lYbwBu.f82OIApQB"),
        (("0123456789abcde", "365"), "lYbwBu.f82OIApQB"),
        (("0123456789abcde", "3333"), "lYbwBu.f82OIApQB"),
        (("0123456789abcde", "3636"), "lYbwBu.f82OIApQB"),
        (("0123456789abcde", "3653"), "lYbwBu.f82OIApQB"),
        (("0123456789abcde", "adm"), "KgKx1UQvdR/09i9u"),
        (("0123456789abcde", "adma"), "KgKx1UQvdR/09i9u"),
        (("0123456789abcde", "user"), "qLopkenJ4WBqxaZN"),
        (("0123456789abcde", "user1234"), "qLopkenJ4WBqxaZN"),
        # 16 char password
        (("0123456789abcdef", ""), ".7nfVBEIEu4KbF/1"),
        (("0123456789abcdef", "36"), ".7nfVBEIEu4KbF/1"),
        (("0123456789abcdef", "365"), ".7nfVBEIEu4KbF/1"),
        (("0123456789abcdef", "3333"), ".7nfVBEIEu4KbF/1"),
        (("0123456789abcdef", "3636"), ".7nfVBEIEu4KbF/1"),
        (("0123456789abcdef", "3653"), ".7nfVBEIEu4KbF/1"),
        (("0123456789abcdef", "user"), ".7nfVBEIEu4KbF/1"),
        (("0123456789abcdef", "user1234"), ".7nfVBEIEu4KbF/1"),
    ]


class cisco_asa_test(_PixAsaSharedTest):
    handler = hash.cisco_asa

    known_correct_hashes = _PixAsaSharedTest.pix_asa_shared_hashes + [
        #
        # passlib reference vectors (ASA-specific)
        #
        # NOTE: See 'pix_asa_shared_hashes' for general PIX+ASA vectors,
        #       and general notes about the 'passlib reference vectors' test set.
        #
        # 13 char password
        # NOTE: past this point, ASA pads to 32 bytes instead of 16
        #       for all cases where user is set (secret + 4 bytes > 16),
        #       but still uses 16 bytes for enable pwds (secret <= 16).
        #       hashes w/ user WON'T match PIX, but "enable" passwords will.
        (("0123456789abc", ""), "eacOpB7vE7ZDukSF"),  # confirmed ASA 9.6
        (("0123456789abc", "36"), "FRV9JG18UBEgX0.O"),
        (("0123456789abc", "365"), "NIwkusG9hmmMy6ZQ"),  # confirmed ASA 9.6
        (("0123456789abc", "3333"), "NmrkP98nT7RAeKZz"),  # confirmed ASA 9.6
        (("0123456789abc", "3636"), "FRV9JG18UBEgX0.O"),  # confirmed ASA 9.6
        (("0123456789abc", "3653"), "NIwkusG9hmmMy6ZQ"),  # confirmed ASA 9.6
        (("0123456789abc", "user"), "8Q/FZeam5ai1A47p"),  # confirmed ASA 9.6
        (("0123456789abc", "user1234"), "8Q/FZeam5ai1A47p"),  # confirmed ASA 9.6
        # 14 char password
        (("0123456789abcd", ""), "6r8888iMxEoPdLp4"),  # confirmed ASA 9.6
        (("0123456789abcd", "3"), "yxGoujXKPduTVaYB"),
        (("0123456789abcd", "36"), "W0jckhnhjnr/DiT/"),
        (("0123456789abcd", "365"), "HuVOxfMQNahaoF8u"),  # confirmed ASA 9.6
        (("0123456789abcd", "3333"), "yxGoujXKPduTVaYB"),  # confirmed ASA 9.6
        (("0123456789abcd", "3636"), "W0jckhnhjnr/DiT/"),  # confirmed ASA 9.6
        (("0123456789abcd", "3653"), "HuVOxfMQNahaoF8u"),  # confirmed ASA 9.6
        (("0123456789abcd", "adm"), "RtOmSeoCs4AUdZqZ"),  # confirmed ASA 9.6
        (("0123456789abcd", "adma"), "RtOmSeoCs4AUdZqZ"),  # confirmed ASA 9.6
        (("0123456789abcd", "user"), "rrucwrcM0h25pr.m"),  # confirmed ASA 9.6
        (("0123456789abcd", "user1234"), "rrucwrcM0h25pr.m"),  # confirmed ASA 9.6
        # 15 char password
        (("0123456789abcde", ""), "al1e0XFIugTYLai3"),  # confirmed ASA 9.6
        (("0123456789abcde", "3"), "nAZrQoHaL.fgrIqt"),
        (("0123456789abcde", "36"), "2GxIQ6ICE795587X"),
        (("0123456789abcde", "365"), "QmDsGwCRBbtGEKqM"),  # confirmed ASA 9.6
        (("0123456789abcde", "3333"), "nAZrQoHaL.fgrIqt"),  # confirmed ASA 9.6
        (("0123456789abcde", "3636"), "2GxIQ6ICE795587X"),  # confirmed ASA 9.6
        (("0123456789abcde", "3653"), "QmDsGwCRBbtGEKqM"),  # confirmed ASA 9.6
        (("0123456789abcde", "adm"), "Aj2aP0d.nk62wl4m"),  # confirmed ASA 9.6
        (("0123456789abcde", "adma"), "Aj2aP0d.nk62wl4m"),  # confirmed ASA 9.6
        (("0123456789abcde", "user"), "etxiXfo.bINJcXI7"),  # confirmed ASA 9.6
        (("0123456789abcde", "user1234"), "etxiXfo.bINJcXI7"),  # confirmed ASA 9.6
        # 16 char password
        (("0123456789abcdef", ""), ".7nfVBEIEu4KbF/1"),  # confirmed ASA 9.6
        (("0123456789abcdef", "36"), "GhI8.yFSC5lwoafg"),
        (("0123456789abcdef", "365"), "KFBI6cNQauyY6h/G"),  # confirmed ASA 9.6
        (("0123456789abcdef", "3333"), "Ghdi1IlsswgYzzMH"),  # confirmed ASA 9.6
        (("0123456789abcdef", "3636"), "GhI8.yFSC5lwoafg"),  # confirmed ASA 9.6
        (("0123456789abcdef", "3653"), "KFBI6cNQauyY6h/G"),  # confirmed ASA 9.6
        (("0123456789abcdef", "user"), "IneB.wc9sfRzLPoh"),  # confirmed ASA 9.6
        (("0123456789abcdef", "user1234"), "IneB.wc9sfRzLPoh"),  # confirmed ASA 9.6
        # 17 char password
        # NOTE: past this point, ASA pads to 32 bytes instead of 16
        #       for ALL cases, since secret > 16 bytes even for enable pwds;
        #       and so none of these rest here should match PIX.
        (("0123456789abcdefq", ""), "bKshl.EN.X3CVFRQ"),  # confirmed ASA 9.6
        (("0123456789abcdefq", "36"), "JAeTXHs0n30svlaG"),
        (("0123456789abcdefq", "365"), "4fKSSUBHT1ChGqHp"),  # confirmed ASA 9.6
        (("0123456789abcdefq", "3333"), "USEJbxI6.VY4ecBP"),  # confirmed ASA 9.6
        (("0123456789abcdefq", "3636"), "JAeTXHs0n30svlaG"),  # confirmed ASA 9.6
        (("0123456789abcdefq", "3653"), "4fKSSUBHT1ChGqHp"),  # confirmed ASA 9.6
        (("0123456789abcdefq", "user"), "/dwqyD7nGdwSrDwk"),  # confirmed ASA 9.6
        (("0123456789abcdefq", "user1234"), "/dwqyD7nGdwSrDwk"),  # confirmed ASA 9.6
        # 27 char password
        (("0123456789abcdefqwertyuiopa", ""), "4wp19zS3OCe.2jt5"),  # confirmed ASA 9.6
        (("0123456789abcdefqwertyuiopa", "36"), "PjUoGqWBKPyV9qOe"),
        (
            ("0123456789abcdefqwertyuiopa", "365"),
            "bfCy6xFAe5O/gzvM",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopa", "3333"),
            "rd/ZMuGTJFIb2BNG",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopa", "3636"),
            "PjUoGqWBKPyV9qOe",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopa", "3653"),
            "bfCy6xFAe5O/gzvM",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopa", "user"),
            "zynfWw3UtszxLMgL",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopa", "user1234"),
            "zynfWw3UtszxLMgL",
        ),  # confirmed ASA 9.6
        # 28 char password
        # NOTE: past this point, ASA stops appending the username AT ALL,
        #       even though there's still room for the first few chars.
        (("0123456789abcdefqwertyuiopas", ""), "W6nbOddI0SutTK7m"),  # confirmed ASA 9.6
        (("0123456789abcdefqwertyuiopas", "36"), "W6nbOddI0SutTK7m"),
        (
            ("0123456789abcdefqwertyuiopas", "365"),
            "W6nbOddI0SutTK7m",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopas", "user"),
            "W6nbOddI0SutTK7m",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopas", "user1234"),
            "W6nbOddI0SutTK7m",
        ),  # confirmed ASA 9.6
        # 32 char password
        # NOTE: this is max size that ASA allows, and throws error for larger
        (
            ("0123456789abcdefqwertyuiopasdfgh", ""),
            "5hPT/iC6DnoBxo6a",
        ),  # confirmed ASA 9.6
        (("0123456789abcdefqwertyuiopasdfgh", "36"), "5hPT/iC6DnoBxo6a"),
        (
            ("0123456789abcdefqwertyuiopasdfgh", "365"),
            "5hPT/iC6DnoBxo6a",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopasdfgh", "user"),
            "5hPT/iC6DnoBxo6a",
        ),  # confirmed ASA 9.6
        (
            ("0123456789abcdefqwertyuiopasdfgh", "user1234"),
            "5hPT/iC6DnoBxo6a",
        ),  # confirmed ASA 9.6
    ]


class cisco_type7_test(HandlerCase):
    handler = hash.cisco_type7
    salt_bits = 4
    salt_type = int

    known_correct_hashes = [
        #
        # http://mccltd.net/blog/?p=1034
        #
        ("secure ", "04480E051A33490E"),
        #
        # http://insecure.org/sploits/cisco.passwords.html
        #
        (
            "Its time to go to lunch!",
            "153B1F1F443E22292D73212D5300194315591954465A0D0B59",
        ),
        #
        # http://blog.ioshints.info/2007/11/type-7-decryption-in-cisco-ios.html
        #
        ("t35t:pa55w0rd", "08351F1B1D431516475E1B54382F"),
        #
        # http://www.m00nie.com/2011/09/cisco-type-7-password-decryption-and-encryption-with-perl/
        #
        ("hiImTesting:)", "020E0D7206320A325847071E5F5E"),
        #
        # http://packetlife.net/forums/thread/54/
        #
        ("cisco123", "060506324F41584B56"),
        ("cisco123", "1511021F07257A767B"),
        #
        # source ?
        #
        ("Supe&8ZUbeRp4SS", "06351A3149085123301517391C501918"),
        #
        # custom
        #
        # ensures utf-8 used for unicode
        (UPASS_TABLE, "0958EDC8A9F495F6F8A5FD"),
    ]

    known_unidentified_hashes = [
        # salt with hex value
        "0A480E051A33490E",
        # salt value > 52. this may in fact be valid, but we reject it for now
        # (see docs for more).
        "99400E4812",
    ]

    def test_90_decode(self):
        """test cisco_type7.decode()"""
        from passlib.utils import to_unicode, to_bytes

        handler = self.handler
        for secret, hashed in self.known_correct_hashes:
            usecret = to_unicode(secret)
            bsecret = to_bytes(secret)
            assert handler.decode(hashed) == usecret
            assert handler.decode(hashed, None) == bsecret

        with pytest.raises(UnicodeDecodeError):
            handler.decode("0958EDC8A9F495F6F8A5FD", "ascii")

    def test_91_salt(self):
        """test salt value border cases"""
        handler = self.handler
        with pytest.raises(TypeError):
            handler(salt=None)
        handler(salt=None, use_defaults=True)
        with pytest.raises(TypeError):
            handler(salt="abc")
        with pytest.raises(ValueError):
            handler(salt=-10)
        with pytest.raises(ValueError):
            handler(salt=100)

        with pytest.raises(TypeError):
            handler.using(salt="abc")
        with pytest.raises(ValueError):
            handler.using(salt=-10)
        with pytest.raises(ValueError):
            handler.using(salt=100)
        with pytest.warns(match="salt/offset must be.*"):
            subcls = handler.using(salt=100, relaxed=True)
        assert subcls(use_defaults=True).salt == 52
