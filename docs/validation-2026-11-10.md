# Validation — 10 November 2026

The concern-based local build was reviewed before the first push.

## Fixes made

- Reject malformed requests and source records without an internal server error.
- Load service results beyond the first page.
- Respect online-service publication flags and reject invalid links.
- Clear the previous location when an invalid map point is selected.
- Check the coordinate system before offering directions.
- Keep retry and return controls after detail failures; retain available service links if an authority request fails.
- Move keyboard focus to new results and keep the info popover inside a narrow screen.
- Include collapsed details when printing, then restore their state.
- Label source descriptions and record dates more clearly.

## Checks completed

**18 Python tests and 3 frontend behaviour tests passed.** JavaScript syntax and whitespace checks also passed.

The browser review covered `Pass` in Mainz, location confirmation, loading a second result page, opening `Reisepass beantragen`, and switching to English. Keyboard selection and a 390-pixel layout were checked. The print-state logic passed a frontend test; the actual printed page still needs visual review in a regular browser.

Live API checks also returned results for `Personalausweis` in Munich, `Gewerbe anmelden` in Hamburg and `Auto anmelden` in Oppenheim. These checks confirm those requests worked; they do not establish that every listed office handles every case.

## Open findings

Some tested records had no opening hours or contacts. Large cities returned several offices or a general authority address. Municipal matching cannot resolve every district or street-specific rule. Broad searches such as `Pass` can place the relevant service late in the list; the source controls ranking.

Remaining work is tracked in [#1: demo checks](https://github.com/KTV02/GdiHackathonChallenge4/issues/1), [#2: shared operation](https://github.com/KTV02/GdiHackathonChallenge4/issues/2) and [#3: matching](https://github.com/KTV02/GdiHackathonChallenge4/issues/3).
