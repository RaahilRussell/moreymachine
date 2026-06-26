# UI / UX Spec

MoreyMachine should look and behave like a front-office decision tool. It should
open with decisions, not a raw dataframe.

## Layout Rules

- Use wide layout.
- Sidebar owns global controls: team, benchmark, quick player search, artifact
  status.
- Each page starts with a short header and summary cards.
- Action cards and player cards come before tables.
- Evidence and raw rows sit lower on the page or inside expanders.
- Empty states explain what is missing and show an exact command.
- Every repeated widget has a stable key.

## Page Structure

Each page should roughly follow:

1. Header.
2. Summary cards.
3. Recommendation or interpretation cards.
4. Filters/selectors.
5. Detail tables.
6. Evidence expanders.

The app should never open a page with a wall of columns before explaining what
the user should look at.

## Core Components

The app component module should provide:

- page header;
- metric card;
- status badge;
- confidence badge;
- score badge;
- score bar;
- empty state;
- warning box;
- manual review box;
- action card;
- move card;
- player header;
- player summary card;
- score breakdown;
- help areas;
- does-not-help;
- core fit cards;
- salary card;
- scenario cards;
- evidence table;
- benchmark card;
- gap card;
- team level card;
- filter panel.

## Target Board UX

Target Board v2 is segmented. Every tab should:

- explain what the segment means;
- show a clean empty state when no rows match;
- show top options before the table;
- keep filters scoped to that tab through unique widget keys;
- include a player selector that can jump to Player Detail.

## Player Detail UX

Player Detail should answer:

- Why is he ranked there?
- What does he help?
- What does he not help?
- What role would he play on this roster?
- How does he fit with the core?
- What is the salary/acquisition reality?
- What scenario makes him useful?
- What could make the recommendation wrong?
- What evidence supports each claim?

## Manual Review UX

Manual review is a first-class product state. The app should not hide stale
contracts, status conflicts, missing salary fields, unsupported claims, or low
confidence. It should group them and show refresh/review commands.
