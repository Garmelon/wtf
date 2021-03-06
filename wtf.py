import asyncio
import logging
import re

import yaboli

if __name__ == "__main__":
    from wtfdb import WtfDB
else:
    from .wtfdb import WtfDB

logger = logging.getLogger(__name__)

class Wtf(yaboli.Module):
    MAX_TERMS = 5
    MAX_TERM_LENGTH = 1024
    MAX_EXPLANATIONS = 15
    MAX_EXPLANATION_LENGTH = 1024

    DESCRIPTION = ("a database of explanations for words, acronyms and"
            " initialisms")
    HELP_GENERAL = DESCRIPTION
    HELP_SPECIFIC = [
            "'wtf' is a database of explanations for words, acronyms and"
            " initialisms. It is inspired by the linux wtf program and uses"
            " its acronyms, in addition to ones set by users.",
            "",
            "!wtf is <term> - look up a term (also responds to 'wtf is')",
            "!wtf add <term> <explanation> - add a new explanation",
            "!wtf detail <term> - shows more info about the term's explanations",
            "!wtf delete <id> - delete explanation with corresponding id (look"
            " up the id using !wtf detail)",
            "!wtf replace <id> <explanation> - a shortcut for deleting and"
            " re-adding with a different explanation",
            "",
            "Uses most acronyms of arch's community/wtf package.",
            "Made by @Garmy using https://github.com/Garmelon/yaboli.",
    ]

    SECTION = "wtf"

    RE_IS      = re.compile(r"\s*is\s+(.*)")
    RE_ADD     = re.compile(r"\s*add\s+(\S+)\s+(.+)")
    RE_DETAIL  = re.compile(r"\s*detail\s+(.*)")
    RE_DELETE  = re.compile(r"\s*delete\s+(\d+)\s*")
    RE_REPLACE = re.compile(r"\s*replace\s+(\d+)\s+(.+)")

    RE_WTF_IS = re.compile(r"\s*wtf\s+is\s+(.*)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        dbfile = self.config[self.SECTION]["db"]
        self.db = WtfDB(dbfile)

        if self.standalone:
            self.register_botrulez(kill=True, restart=True)

        self.register_general("wtf", self.cmd_wtf)

    def _format_explanations(self, explanations, detail=False):
        # Id, Term, Explanation, Author
        if detail:
            explanations = [f"{i}: {t} — {e} (by {a})" for i, t, e, a in explanations]
        else:
            explanations = [f"{t} — {e}" for _, t, e, _ in explanations]

        if len(explanations) > self.MAX_EXPLANATIONS:
            message = ("Some explanations were omitted because this bot only"
                    f" displays {self.MAX_EXPLANATIONS} explanations per"
                    " term.")
            explanations = explanations[:-1] + [message]

        return explanations

    async def _find_explanations(self, terms, detail=False):
        lines = []
        for term in terms:
            explanations = await self.db.find_full(term, self.MAX_EXPLANATIONS + 1)
            if explanations:
                lines.extend(self._format_explanations(explanations, detail=detail))
            else:
                lines.append(f"{term!r} not found.")
        return lines

    async def send_explanations(self, message, termstr):
        terms = [term for term in termstr.split() if term]
        terms = terms[:self.MAX_TERMS]

        if not terms: return

        if max(map(len, terms)) > self.MAX_TERM_LENGTH:
            await message.reply(("A term can be at most"
                    f" {self.MAX_TERM_LENGTH} characters long."))
            return

        lines = await self._find_explanations(terms)
        await message.reply("\n".join(lines))
        return

    async def on_send(self, room, message):
        await super().on_send(room, message)

        match = self.RE_WTF_IS.fullmatch(message.content)
        if match:
            terms = match.group(1)
            await self.send_explanations(message, terms)

    async def cmd_wtf(self, room, message, args):
        match_is = self.RE_IS.fullmatch(args.raw)
        if match_is:
            terms = match_is.group(1)
            await self.send_explanations(message, terms)
            return

        match_add = self.RE_ADD.fullmatch(args.raw)
        if match_add:
            term = match_add.group(1)
            explanation = match_add.group(2).strip()

            if len(term) > self.MAX_TERM_LENGTH:
                await message.reply(("A term can be at most"
                        f" {self.MAX_TERM_LENGTH} characters long."))
                return

            if len(explanation) > self.MAX_EXPLANATION_LENGTH:
                await message.reply(("An explanation can be at most"
                        f" {self.MAX_EXPLANATION_LENGTH} characters long."))
                return

            await self.db.add(term, explanation, message.sender.nick)
            logger.info((f"{message.sender.atmention} added explanation:"
                f" {term} - {explanation}"))
            await message.reply(f"Added explanation: {term} — {explanation}")
            return

        match_detail = self.RE_DETAIL.fullmatch(args.raw)
        if match_detail:
            terms = match_detail.group(1)
            terms = [term for term in terms.split() if term]
            if not terms: return
            lines = await self._find_explanations(terms, detail=True)
            await message.reply("\n".join(lines))
            return

        match_delete = self.RE_DELETE.fullmatch(args.raw)
        if match_delete:
            aid = match_delete.group(1)
            await self.db.delete(aid)
            logger.info((f"{message.sender.atmention} deleted explanation with"
                " id {aid}"))
            await message.reply(f"Deleted.")
            return

        match_replace = self.RE_REPLACE.fullmatch(args.raw)
        if match_replace:
            aid = match_replace.group(1)
            explanation = match_replace.group(2).strip()

            if len(explanation) > self.MAX_EXPLANATION_LENGTH:
                await message.reply(("An explanation can be at most"
                        f" {self.MAX_EXPLANATION_LENGTH} characters long."))
                return

            term = await self.db.get(aid)
            if term is None:
                await message.reply(f"No explanation with id {aid} exists.")
            else:
                await self.db.delete(aid)
                logger.info((f"{message.sender.atmention} deleted explanation"
                        f" with id {aid}"))
                await self.db.add(term, explanation, message.sender.nick)
                logger.info((f"{message.sender.atmention} added explanation:"
                        f" {term} - {explanation}"))
                await message.reply(f"Changed explanation: {term} — {explanation}")
            return

        # else...
        await message.reply("Incorrect command, see the !help for details.")


if __name__ == "__main__":
    yaboli.enable_logging(level=logging.DEBUG)
    yaboli.run(Wtf)
