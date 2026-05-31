# Chapter 6 — Admissible sets and the questions you can ask them

There's one concept underneath every framework call. It's called
the **admissible set**. Once you understand what an admissible
set is, you understand what the framework is really computing.

I'm going to introduce this idea slowly and concretely. The
name sounds technical. The idea isn't.

## A puzzle to start

Take three coins. Lay them down in a row. Each coin can be
heads or tails. How many distinct ways can you arrange them?

Answer: eight. Three coins, each with two choices, gives
2 × 2 × 2 = 8. They are HHH, HHT, HTH, HTT, THH, THT, TTH, TTT.

Now I add a rule: *the number of heads must be even*. How
many arrangements satisfy that rule?

Answer: four. They are HHT-no-wait. Let me redo. Even number of
heads = 0 or 2. With 0 heads: TTT (one way). With 2 heads:
HHT, HTH, THH (three ways). So four arrangements satisfy the
rule.

The set `{HHT, HTH, THH, TTT}` is what the framework would call
the **admissible set** for this rule. The whole world of
possible coin arrangements has 8 elements; the admissible set
— the ones that pass the rule — has 4.

That's the concept. *The admissible set is the subset of all
possible configurations that satisfy your rules.* You hand the
framework the rules. The framework reasons about the admissible
set.

## What the framework lets you ask about admissible sets

Once you've defined an admissible set (by specifying the rules
that determine it), there are *only a handful of fundamentally
different questions* you can ask. The framework has methods for
each of them.

### Question 1 — How many?

The simplest question. How many elements are in the admissible
set?

In the coin example, the answer is 4. The framework's method
for this kind of question is `count_solutions` for constraint
sets, or `count_matchings` for graph problems.

The point is: *you don't iterate*. You don't write a `for`
loop that goes through all 2³ = 8 possibilities and counts
the ones that pass. You hand the framework the rules and it
returns the count, computed directly. For 3 coins this seems
overkill. For 100 coins (where the brute-force enumeration
would visit 2¹⁰⁰ ≈ 10³⁰ possibilities), it makes the
difference between "answer in milliseconds" and "answer never".

### Question 2 — Give me a specific one (a "witness")

Sometimes you don't want a count. You want a specific element
of the admissible set as proof that one exists, or as a
starting point for further work.

In the coin example, asking for a *witness* might return
"HHT" — a specific arrangement that has 2 heads (even).

The framework's method for this is `witness` for graphs,
`find_witness_solution` for constraint sets.

A witness is more useful than you might think. Many real
problems decompose into *"is there at least one configuration
that satisfies these conditions, and if so, show me one"*. A
witness gives you that immediately.

### Question 3 — What's the cheapest one (or the best one)?

Now suppose each element of the admissible set has a **cost**
attached. Maybe in the coin example, each H costs 1 and each T
costs 3. The cost of an arrangement is the sum across the three
coins. With this rule, the costs of the four admissible
arrangements are:

- HHT: 1 + 1 + 3 = 5
- HTH: 1 + 3 + 1 = 5
- THH: 3 + 1 + 1 = 5
- TTT: 3 + 3 + 3 = 9

The cheapest is one of HHT, HTH, or THH (all tied at 5). The
framework's method for this kind of question is
`min_weight_matching` (when the admissible set is the set of
perfect matchings of a graph) or `min_cost_schedule`,
`min_cost_flow`, etc., for other shapes.

This is what Chapter 3 called "the surprising word" — the
**semiring choice**. The same machinery that counts the
admissible set's elements can also pick the cheapest one,
or the heaviest one, or check whether one exists, just by
swapping out the arithmetic operations underneath.

### Question 4 — What's the probability of being in this set under random conditions?

This is a more subtle question. Imagine each rule about the
admissible set might be *broken* with some probability. What's
the probability that, under random rule-breakings, the
admissible set becomes empty (or shrinks to below some
threshold)?

In the coin example, suppose each coin has a 10% chance of
being mis-printed (its head/tail flipped). What's the
probability that the resulting arrangement still has an even
number of heads?

The framework's `tail_probability` method computes this kind of
thing exactly. The general pattern is: *given some uncertainty
in the inputs, what's the probability the admissible set still
contains a valid configuration?*

### Question 5 — Which inputs are critical?

Looking back at the rules that define an admissible set,
*which of those rules, if removed, would change the answer
dramatically?* These are the **critical inputs**. The
framework's `single_points_of_failure` method finds them for
matching problems.

In real applications, this is enormously valuable. It tells
you *which edges of your network are critical*, *which
constraints are binding*, *which components, if they failed,
would cause the whole system to fail*.

## Five questions, infinite applications

So you have five distinct kinds of questions you can ask about
an admissible set:

1. **How many?** — `count_*`
2. **Give me one.** — `witness`, `find_witness_solution`
3. **Which is best/cheapest?** — `min_*`, `max_*`
4. **What's the probability under uncertainty?** — `tail_probability`
5. **Which inputs matter most?** — `single_points_of_failure`

And here's the magic: *every application of the framework
across every domain reduces to one of these five questions
applied to some admissible set*.

A reinsurance treaty exposure calculation? It's question 4
(probability of large loss) on the admissible set of
"earthquake scenarios that affect this portfolio". A factory
schedule? Question 3 (cheapest) on the admissible set of
"valid job-to-machine assignments". A workflow audit? Question
1 (how many reachable terminal states) plus question 5
(which steps are critical) on the admissible set of "valid
execution traces".

Once you see this, the framework's API stops feeling like a
grab-bag of unrelated methods and starts feeling like a
small, coherent set of questions you can ask in many
different domains.

## Why this matters: the difference between the framework and a database

In some ways, the admissible set is the framework's analogue of
the database table. A database table is a set of records you
can ask questions about. An admissible set is a set of
configurations you can ask the same five questions about. SQL
asks how-many, find-one, find-extreme. So does this framework.

The difference is what *defines* the set. A database table is
defined by *what you put in it* — explicit data. An admissible
set is defined by *the rules that constrain it* — implicit
data. You never write down the admissible set explicitly
(often it's astronomically large; the coin example with 100
coins has 2¹⁰⁰ ≈ 10³⁰ possible arrangements, way more than
fits in any database). You just write down the rules. The
framework reasons about the set without ever materialising it.

This is why the framework can answer questions about
admissible sets with 10³⁰ elements in milliseconds. It never
looks at them all. It exploits the structure of the rules to
compute the answers directly.

## What the framework needs in order to do this

The framework doesn't handle every kind of admissible set. It
needs the set to have **structure** — specifically, the kind
of structure introduced in Chapter 4 (planar graphs, GF(2)-
affine constraint sets, matchgate-realisable signatures).

When the structure is there, the framework can answer the five
questions in polynomial time. When the structure isn't there,
the framework honest-stops. That's the whole story.

This is also where the SQL analogy breaks down a bit. SQL
works on *any* tabular data, no matter how the table is
structured internally. The framework's admissible sets need
to have the right structural shape. The good news: a lot of
real-world admissible sets *do* have the right shape, and the
framework's classifier (Chapter 7) detects this for you.

## A picture in your head

If you take one thing from this chapter, take this picture:

> A framework call says *"here is an admissible set, defined
> by these rules. Answer this kind of question about it."*
> The framework reads the rules, recognises the structural
> shape of the resulting set, picks the right algorithm under
> the floor, and returns the answer.

You will write code like:

```python
sc.count_matchings(graph)
```

In your head, what's happening is:

> *Graph defines an admissible set (the set of perfect
> matchings of the graph). The question is "how many?". The
> framework picks Kasteleyn-Pfaffian as the right algorithm
> because the graph is planar. The number comes back exact.*

That's the mental model. The next chapter — Chapter 7 — opens
up the box that picks the algorithm. It's called the
classifier, and it's how the framework figures out which
algorithm fits which problem.

## Pause point

This is a good place to pause. If the idea of the admissible
set hasn't quite clicked, try this exercise:

Pick something you work with that has rules. A scheduling
constraint set at your job. A workflow definition. The traffic
laws of your city. Whatever.

Then ask:

- *What configurations satisfy all the rules?* That's the
  admissible set.
- *Which of the five questions (count, witness, best,
  probability, critical) would you naturally want to ask about
  this admissible set?*
- *How would you compute the answer today, with the tools you
  have?*

Most readers, after doing this exercise, find at least one
admissible set they'd love to ask the framework about. That's
the entry point.

The next chapter explains what happens when you do.
