"""passlib.crypto._blowfish._gen_files - meta script that generates unrolled.py"""

# core
import os
import textwrap
# pkg
# local


def varlist(name, count):
    return ", ".join(name + str(x) for x in range(count))


def indent_block(block, padding):
    """ident block of text"""
    lines = block.split("\n")
    return "\n".join(padding + line if line else "" for line in lines)


BFSTR = """\
                ((((S0[l >> 24] + S1[(l >> 16) & 0xff]) ^ S2[(l >> 8) & 0xff]) +
                  S3[l & 0xff]) & 0xffffffff)
""".strip()


def render_encipher(write, indent=0):
    for i in range(0, 15, 2):
        write(
            indent,
            """\
            # Feistel substitution on left word (round %(i)d)
            r ^= %(left)s ^ p%(i1)d

            # Feistel substitution on right word (round %(i1)d)
            l ^= %(right)s ^ p%(i2)d
        """,
            i=i,
            i1=i + 1,
            i2=i + 2,
            left=BFSTR,
            right=BFSTR.replace("l", "r"),
        )


def write_encipher_function(write, indent=0):
    write(
        indent,
        """\
        def encipher(self, l, r):
            \"""blowfish encipher a single 64-bit block encoded as two 32-bit ints\"""

            (p0, p1, p2, p3, p4, p5, p6, p7, p8, p9,
              p10, p11, p12, p13, p14, p15, p16, p17) = self.P
            S0, S1, S2, S3 = self.S

            l ^= p0

            """,
    )
    render_encipher(write, indent + 1)

    write(
        indent + 1,
        """\

        return r ^ p17, l

        """,
    )


def write_expand_function(write, indent=0):
    write(
        indent,
        """\
        def expand(self, key_words):
            \"""unrolled version of blowfish key expansion\"""
            ##assert len(key_words) >= 18, "size of key_words must be >= 18"

            P, S = self.P, self.S
            S0, S1, S2, S3 = S

            #=============================================================
            # integrate key
            #=============================================================
        """,
    )
    for i in range(18):
        write(
            indent + 1,
            """\
            p%(i)d = P[%(i)d] ^ key_words[%(i)d]
        """,
            i=i,
        )
    write(
        indent + 1,
        """\

        #=============================================================
        # update P
        #=============================================================

        #------------------------------------------------
        # update P[0] and P[1]
        #------------------------------------------------
        l, r = p0, 0

        """,
    )

    render_encipher(write, indent + 1)

    write(
        indent + 1,
        """\

        p0, p1 = l, r = r ^ p17, l

        """,
    )

    for i in range(2, 18, 2):
        write(
            indent + 1,
            """\
            #------------------------------------------------
            # update P[%(i)d] and P[%(i1)d]
            #------------------------------------------------
            l ^= p0

            """,
            i=i,
            i1=i + 1,
        )

        render_encipher(write, indent + 1)

        write(
            indent + 1,
            """\
            p%(i)d, p%(i1)d = l, r = r ^ p17, l

            """,
            i=i,
            i1=i + 1,
        )

    write(
        indent + 1,
        """\

        #------------------------------------------------
        # save changes to original P array
        #------------------------------------------------
        P[:] = (p0, p1, p2, p3, p4, p5, p6, p7, p8, p9,
          p10, p11, p12, p13, p14, p15, p16, p17)

        #=============================================================
        # update S
        #=============================================================

        for box in S:
            j = 0
            while j < 256:
                l ^= p0

        """,
    )

    render_encipher(write, indent + 3)

    write(
        indent + 3,
        """\

                box[j], box[j+1] = l, r = r ^ p17, l
                j += 2
        """,
    )


def main():
    target = os.path.join(os.path.dirname(__file__), "unrolled.py")
    with open(target, "w") as fh:

        def write(indent, msg, **kwds):
            literal = kwds.pop("literal", False)
            if kwds:
                msg %= kwds
            if not literal:
                msg = textwrap.dedent(msg.rstrip(" "))
            if indent:
                msg = indent_block(msg, " " * (indent * 4))
            fh.write(msg)

        write(
            0,
            """\
            \"""passlib.crypto._blowfish.unrolled - unrolled loop implementation of bcrypt,
            autogenerated by _gen_files.py

            currently this override the encipher() and expand() methods
            with optimized versions, and leaves the other base.py methods alone.
            \"""
            #=================================================================
            # imports
            #=================================================================
            # pkg
            from passlib.crypto._blowfish.base import BlowfishEngine as _BlowfishEngine
            # local
            __all__ = [
                "BlowfishEngine",
            ]
            #=================================================================
            #
            #=================================================================
            class BlowfishEngine(_BlowfishEngine):

            """,
        )

        write_encipher_function(write, indent=1)
        write_expand_function(write, indent=1)

        write(
            0,
            """\
                #=================================================================
                # eoc
                #=================================================================

            #=================================================================
            # eof
            #=================================================================
            """,
        )


if __name__ == "__main__":
    main()
