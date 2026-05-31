# Chapter 2 — The SQL story, retold

If you've programmed for any length of time, you've used SQL.
You've probably written something like `SELECT name FROM
customers WHERE state = 'CA'`. You probably didn't think much
of it. SQL is just *there*. It's how you talk to databases.

I want to tell you a story about how SQL came to be there,
because the same story is starting to play out, right now, for
a different kind of computation. If you understand how SQL won,
you'll have a good sense of what to expect from this new
paradigm — what's likely to happen, on what timeline, and what
the practical wins look like along the way.

The chapter is in two parts:

1. **What programming looked like before SQL.** A short, vivid
   picture of how horrible the old way was.
2. **How SQL took over.** The five-stage path from "weird
   academic idea" to "industry default".

That's the same arc that the framework in this book is
travelling. Today, it's somewhere around Stage 2.

## What programming looked like before SQL

It's 1972. You work as a programmer at a mid-sized US company
that sells widgets. Your boss walks up to your desk and asks:

> *"How many of our California customers bought a widget last
> month and still owe us more than $1,000?"*

That sounds like a question that should take you a minute to
answer. In 1972, it takes you the better part of a morning.

Here's what you have to do. The company's customer data is
stored in two big files on a mainframe disk: a `customers.dat`
file and an `orders.dat` file. Both files are just streams of
fixed-width records — name, address, ID, balance for customers;
date, customer ID, product, amount for orders.

You sit down to write the code. Here's roughly what it has to
do. (I'll show you a COBOL-ish pseudocode; the real thing was
worse.)

```
Open customers.dat
Read the first customer record
While not at the end of customers.dat:
  If the customer's state is "CA":
    Open orders.dat
    Read the first order record
    Set a flag "found_widget" to false
    While not at the end of orders.dat:
      If this order's customer_id matches AND
         the order is a widget AND
         the order date is within the last month:
        Set "found_widget" to true
        Stop reading orders.dat
      Read the next order record
    Close orders.dat
    If found_widget is true AND
       this customer's balance is more than $1000:
      Increment counter
  Read the next customer record
Close customers.dat
Print the counter
```

About thirty lines of code. The thirty lines say *how* to get
the answer: open the customer file; for each Californian, open
the orders file; look through it for a widget order; close the
file; check the balance; move on. You're personally choreographing
the disk reads. You're personally choosing the iteration order.
You're personally deciding when to stop and restart.

Tomorrow your boss asks a slightly different question — the
same customers, but now grouped by ZIP code and sorted by total
order value. You go back and write thirty *different* lines of
code. Same files, different iteration logic, different
bookkeeping.

The week after that, your colleague Tony writes ANOTHER thirty
lines for the question *"which customers have ordered every
product we sell at least once?"* — and there's a subtle bug in
his loop logic that takes a week to track down because the bug
only shows up when a customer happens to have a particular
number of orders. The customer file is still the same. Tony
just got the iteration wrong.

Now imagine an entire company doing this for ten years. Every
"data report" the company runs — sales by region, top
customers by lifetime value, products with no orders, anything
— is its own painstaking program with its own iteration logic.
Each one is brittle. Each one has bugs that depend on subtle
properties of the data. Each one has to be rewritten when the
data layout changes. Each one runs slowly unless someone
carefully tunes it.

That's what 100,000 lines of 1970-era data processing code
looks like.

This isn't an exaggeration. Whole departments existed —
sometimes called the **data processing department** — whose
entire job was to write these one-off programs. A "report
request" went into a queue and took two weeks to come back.
Adding a new index to speed up one common query required
rewriting every program that touched the file. Adding a new
column to the customer file required rewriting essentially
every program that read it.

The data processing department was the *infrastructure of the
field*. It was how everyone did everything. Anyone in the
industry in 1972 would have told you it was a hard problem
that probably couldn't be done much better.

They were wrong.

## Edgar Codd and a different idea

In 1970, a mathematician at IBM named Edgar Codd published a
paper called *"A Relational Model of Data for Large Shared Data
Banks"*. The paper made an argument that, at the time, seemed
almost academically self-indulgent: it said you shouldn't have
to write the iteration logic at all.

Codd's argument had three pieces.

**First piece: your data has structure that's worth naming.**
Customer records sit in a customer table. Order records sit in
an order table. There's a *relationship* between them — every
order belongs to a customer. That relationship is data the
computer should know about, not something the programmer should
have to navigate by hand every time.

**Second piece: questions about the data have a natural
declarative form.** Instead of *how to compute* "Californian
widget-buying customers with balances over $1,000", just *say
that*. The "how" can be left to the computer. Codd showed,
mathematically, that almost every interesting question about
tabular data could be written in a small, well-defined
language. He called it the **relational calculus**.

**Third piece: the computer can figure out the "how" by
itself, often better than a human would.** Codd argued that a
piece of software — what we now call a **query optimiser** —
could read the declarative question, look at the data's actual
structure (which columns have indexes? how big are the tables?
which values are common?), and pick a good execution plan
automatically. Sometimes the optimiser would find plans that a
human wouldn't have thought of.

The paper landed in a tiny corner of computer science. Codd's
colleagues at IBM thought it was interesting. Most of the
industry didn't notice.

But IBM Research thought he was onto something. They started
building a prototype. They called it **System R**, and it was
the first software in the world to take Codd's idea seriously.
The language it used was a slightly informal version of what
later became SQL.

Here's what the Californian-widget-buyers question looks like
in SQL:

```sql
SELECT COUNT(*)
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE c.state = 'CA'
  AND o.product = 'WIDGET'
  AND o.date >= DATE('now', '-1 month')
  AND c.balance > 1000;
```

Five lines. Same question. You don't say which file to open
first. You don't write the iteration. You don't decide when to
stop. You just say *what you want*. The database engine
figures out the rest.

If you change the question — different filter, different
grouping, different ordering — you change a few words of the
query and re-run it. If the database adds new indexes, your
query gets faster without any code change. If the database
grows, your query still gives the right answer; it just takes
longer.

## How SQL took over

If Codd had been wrong, this story would end here. He wasn't.
What happened next was a slow, fifteen-year transformation
that completely rewrote how the industry worked.

The pattern that emerged moved through five distinct stages.
Each one took about three years. Here they are, in plain
language.

### Stage 0: The academic insight (1970-1973)

Codd's paper is out. A handful of academics and a small team at
IBM Research take it seriously. Nobody else does. To most
practising programmers, the relational model sounds like
abstract mathematics with no clear relationship to their
day-to-day work.

In this stage the *idea* exists, but you can't buy a product
that uses it. The data processing department is still doing
things the 1970 way.

### Stage 1: The research prototypes (1973-1976)

IBM Research builds **System R**. UC Berkeley independently
builds **INGRES**. These are working software — you can
actually use them — but they're still research projects. Not
sold commercially. Used mostly by their builders and by
adventurous academic collaborators.

The prototypes prove two things:

1. **The query optimiser actually works.** When you write a
   declarative query, the engine really does figure out a good
   execution plan. Often a better one than a human would have
   written by hand.
2. **The performance is competitive.** Early on, hand-tuned
   code was faster than the optimiser. By the end of Stage 1,
   the optimiser had caught up on most queries and surpassed
   humans on complex ones.

These prototypes are what convince a small number of
forward-looking technical leaders that the idea isn't just
academic.

### Stage 2: Commercial products (1976-1979)

In 1977, a small company called Software Development
Laboratories — soon to rename itself **Oracle** — starts
selling the first commercial relational database. IBM follows
with **SQL/DS** in 1981.

In this stage, the products exist but adoption is slow.
Enterprises trying these systems find they're sometimes slow,
sometimes buggy, sometimes don't yet support the SQL features
that practising data programmers want. Most companies stick
with the old way. But the early adopters — the ones who can
tolerate some bugs in exchange for the productivity gain — are
visible enough to start shifting the conversation.

The framework in this book — `structural-computing` — is at
about this stage. It's a real, commercial-grade, installable
package. Early adopters are starting to use it for specific
problems. But most of the world is still doing things the
Monte Carlo way.

### Stage 3: Enterprise migration (1979-1985)

By 1980, Oracle has shipped multiple versions. IBM's DB2
launches in 1983. The data processing departments of major
companies start migrating from their hand-coded systems to
relational databases. There's still resistance — old systems
keep running for years — but new projects are increasingly
SQL-based by default.

This is the stage where the *productivity gains become
undeniable*. A report that used to take two weeks for the data
processing department to deliver now takes five minutes for an
analyst with SQL access. The economic logic becomes
overwhelming.

### Stage 4: Standardisation and infrastructure (1985-1990)

In 1986, the American National Standards Institute (ANSI)
publishes **SQL-86**, the first official standard. In 1989
comes **SQL-89**. By the end of the 1980s, every major
database vendor speaks the same language.

The standardisation does something subtle but enormously
important: it makes the paradigm *invisible*. SQL is no longer
"a thing you choose to learn"; it's "how databases work". A
programmer just absorbs it as part of becoming a programmer.

By 1990, the iteration-code data systems of 1972 are
essentially extinct in new development. Old ones keep running
— some are still running today — but nobody chooses to write a
new system that way.

## What changed, fundamentally

Five things, all happening together, drove the transformation:

**Codebases shrank.** The 100,000-line iteration-code data
modules of 1972 became 1,000 lines of SQL queries by 1985.
Not because the programmers had got better; because the work
itself had shrunk. The data processing department's mountain
of bespoke programs evaporated.

**The skill profile changed.** In 1972, you needed programmers
who could write efficient file-iteration code. By 1985, you
needed analysts who could think about data shapes. Different
people. Different training. A whole new job category — the
**database administrator** — emerged.

**The infrastructure consolidated.** Every database engine had
the same SQL parser, the same query planner, the same general
execution model. The thousand competing iteration libraries
collapsed to about ten databases. The companies that didn't
make that consolidation (and there were many) died.

**Optimisation moved under the floor.** Better algorithms kept
appearing in the optimiser. Your queries got faster without
your changing them. New types of indexes, new join algorithms,
new statistics collection — all happened *underneath* SQL,
without breaking any user code.

**New things became possible.** Reporting tools. Business
intelligence dashboards. Data warehouses. Online analytics.
ORMs that hid the database from application programmers. The
whole stack of tooling we now take for granted *did not exist*
in the iteration-code era — couldn't exist, because the
abstraction wasn't there.

## What this means for the framework

`structural-computing` is in the middle of the same kind of
journey, but for a different problem domain. The domain isn't
tabular data; it's *combinatorial questions on structured
graphs and constraint systems*. The mathematics underneath is
different (Pfaffians and Holant evaluation instead of relational
algebra). But the shape of the journey is the same.

Here's where the parallel stands today:

| Stage | What SQL did | What `structural-computing` is doing |
|---|---|---|
| 0 (insight) | Codd's 1970 paper | The underlying math (FKT, Kasteleyn, Cai-Lu) — well-established, mostly invisible to industry |
| 1 (prototype) | System R, INGRES | `holant-tools` — the math engine. Live on PyPI |
| 2 (commercial library) | Oracle 1977, SQL/DS 1981 | `structural-computing` v1.0 — released 2026. *We are here.* |
| 3 (enterprise migration) | 1980-1985: Fortune 500 starts using SQL | Not yet. This is the next 5 years if the paradigm pans out. |
| 4 (infrastructure) | SQL-86, SQL-89: paradigm becomes default | Not yet. This is the 10-15 year vision. |

So `structural-computing` today is at the same stage Oracle
was at in 1979. The product exists. Early adopters exist.
The mathematical case is solid. The industry, at large, hasn't
caught up. There's enormous productivity available to people
who use the framework now, before the rest of the industry
notices.

That's the practical takeaway: the SQL precedent suggests
this is a window. Early adopters of declarative paradigms have
historically captured outsized productivity gains for ten or
fifteen years before everyone else caught up. If the
parallel holds — and the underlying mathematics suggests it
should — the people who learn this framework in the next few
years will get the same kind of advantage that the early
adopters of SQL got in 1980.

## What you don't have to believe

To get value from the rest of this book, you don't have to
believe `structural-computing` is going to be the new SQL. You
just have to believe three things:

1. There are problems where the exact answer matters and is
   computable.
2. There are real codebases — like Sara's — where huge amounts
   of Monte Carlo machinery exist *because the field thought
   exact was intractable*.
3. The framework is one example of a tool that, when it
   applies, collapses (2) into (1).

If those three are true, then the framework is worth knowing
about today, regardless of what happens in the next fifteen
years. The next chapter explains, in plain words and with
concrete examples, what the framework actually does.
