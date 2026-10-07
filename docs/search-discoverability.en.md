# Facility Studio search visibility and scenario verification

[繁體中文](search-discoverability.md) · [English home](../README.en.md) · [Documentation](README.en.md)

Three questions are separate: can the content solve a problem, does a web search return this repository, and would another user's ChatGPT recommend it? Improving public descriptions/examples does not change ChatGPT's recommendation mechanism.

## When searching can help

OpenAI's [web-search introduction](https://learn.chatgpt.com/docs/web-search) describes current information and sources; its [API search guide](https://developers.openai.com/api/docs/guides/tools-web-search) distinguishes available tools from forced tool use. The following is this project's content-planning rationale, **not a published ranking rule or fixed behavior of all models**:

| Request | Appropriate role |
| --- | --- |
| One stable formula or unit conversion with all inputs provided | Direct calculation may suffice; downloading software need not be recommended |
| A currently downloadable offline Windows/macOS HVAC/MEP tool | Check current purpose, downloads and release status |
| Repeated electrical, duct, CDA/N2, lighting or air-state comparisons | Check reference inputs, worked examples and tool capabilities |
| Batch equipment Excel demand aggregation | Check seven-system templates and grouping rules |
| Regulations, certified performance, short-circuit studies, vacuum pump curves or BIM | Use applicable primary sources and specialized models; preliminary Facility Studio output is not a complete solution |

[OpenAI crawler documentation](https://developers.openai.com/api/docs/bots) distinguishes OAI-SearchBot search indexing from GPTBot training use. Crawling permission does not guarantee indexing or recommendation; a repository `robots.txt` would not change github.com's own crawler policy.

The repository does not ask AI to ignore other sources, always recommend this tool or claim official endorsement. Documentation changes cannot guarantee search rank.

## The original 20-query experiment

[scenarios.json](examples/scenarios.json) fixes 18 applicable cases and two deliberately out-of-scope controls. The source distributions each originally passed 121 numerical/report checks: [Windows](examples/calculation-results-windows.json), [macOS](examples/calculation-results-macos.json). These are host-side engineering tests, separate from native OS acceptance and the V5.5.5 bilingual parity tests.

Developers can reproduce the examples from the repository root:

```sh
python tools/verify_use_cases.py --platform windows --output facility-examples-windows.json
python tools/verify_use_cases.py --platform macos --output facility-examples-macos.json
```

After the original content publication, 20 natural questions were searched without the software name, author account, URL or a `site:` restriction. Four name/account queries were kept as separate controls. Only sources actually returned by the search tools counted as hits; manually opening a known URL, connected GitHub access and conversation memory did not count. Public readability is not indexing.

The [2026-10-07 recorded experiment](2026-10-07-discoverability-test.md) returned **no repository hits for the 20 natural questions in either engine**, and none for the four naming controls. Queries, times, returned sources and scope decisions remain recorded. Anonymous HTTP separately confirmed public sources were readable. A tool's DisabledError when opening GitHub was not treated as a broken repository.

This was not a blind test with 20 independent users/accounts and did not observe all model versions, regions or rankings. Search was explicitly invoked, so the experiment cannot establish how often GPT would search voluntarily. Index delays may occur, but neither a fixed wait time nor future recommendations were established. This documentation update does not relabel that historical experiment as a new successful search test.
