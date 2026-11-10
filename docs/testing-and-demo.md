# Testing and demo

## Quick demo

1. Start the app using the [README](../README.md).
2. Enter `Auto anmelden` and `Schillerplatz, Mainz`. Confirm the correct location, then select `Erstzulassung eines Fahrzeugs (Neuzulassung) beantragen`.
3. Check the authority's address, contacts, opening hours and online-service links. Open the source information and try the print button.
4. Try the language switch and a point chosen on the map. Use `Pass` to check loading further service results.

These examples worked in the local review on 10 November 2026. Live data can change; check the selected location and official portal before presenting.

## Automated checks

```bash
python -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

The frontend checks require Node.js 20+. They test selected state changes without a browser. They do not replace checks of rendering, screen readers or actual printed output.

The [validation record](validation-2026-11-10.md) contains the last results. Remaining demo checks are tracked in [issue #1](https://github.com/KTV02/GdiHackathonChallenge4/issues/1); matching improvements are in [#3](https://github.com/KTV02/GdiHackathonChallenge4/issues/3).
