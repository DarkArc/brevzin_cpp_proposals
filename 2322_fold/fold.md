---
title: "`ranges::fold`"
document: P2322R5
date: today
audience: LEWG
author:
    - name: Barry Revzin
      email: <barry.revzin@gmail.com>
toc: true
---

# Revision History

Since [@P2322R4], removed the short-circuiting fold with one that simply returns the end iterator in addition to the value. Also removed the projections, see [the discussion](#no-projections).

Since [@P2322R3], no changes in actual proposal, just some improvements in the description.

[@P2322R2] used the names `fold_left` and `fold_right` to refer to the left- and right- folds and used the same names for the initial value and no-initial value algorithms. LEWG took the following polls [@P2322-minutes]:

* `fold` with an initial value, and `fold` with no initial value and non-empty range should have different names (presumably `fold` and `fold_first`)

|SF|F|N|A|SA|
|-|-|-|-|-|
|6|6|3|2|1|

* Rename `fold_left` to `fold`

|SF|F|N|A|SA|
|-|-|-|-|-|
|2|10|8|3|1|

This revision uses different names for the initial value and no-initial value algorithms, although rather than using `fold` and `fold_right` (and coming up with how to name the no-initial value versions), this paper uses the names `foldl` and `foldr` and then `foldl1` and `foldr1`. This revision also changes the no-initial value versions from having a non-empty range as a precondition to instead returning `optional<T>`.

There was also discussion around having these algorithms return an end iterator.

* Return the end iterator in addition to the result

|SF|F|N|A|SA|
|-|-|-|-|-|
|2|3|5|4|6|

* Have a version of the fold algorithms that return the end iterator in addition to the result (as either an additional set of functions, or having some of the versions have different return values)

|SF|F|N|A|SA|
|-|-|-|-|-|
|4|9|3|3|1|

But the primary algorithms (`foldl` and `foldl1` for left-fold) will definitely solely return a value. This revision adds further discussion on the flavors of `fold` that can be provided, and ultimately adds another pair that satisfies this desire.

[@P2322R1] used _`weakly-assignable-from`_ as the constraint, this elevates it to `assignable_from`. This revision also changes the return type of `fold` to no longer be the type of the initial value, see [the discussion](#return-type).

[@P2322R0] used `regular_invocable` as the constraint in the `@*foldable*@` concept, but we don't need that for this algorithm and it prohibits reasonable uses like a mutating operation. `invocable` is the sufficient constraint here (in the same way that it is for `for_each`). Also restructured the API to overload on providing the initial value instead of having differently named algorithms.

# Introduction

As described in [@P2214R0], there is one very important rangified algorithm missing from the standard library: `fold`.

While we do have an iterator-based version of `fold` in the standard library, it is currently named `accumulate`, defaults to performing `+` on its operands, and is found in the header `<numeric>`. But `fold` is much more than addition, so as described in the linked paper, it's important to give it the more generic name and to avoid a default operator.

Also as described in the linked paper, it is important to avoid over-constraining `fold` in a way that prevents using it for heterogeneous folds. As such, the `fold` specified in this paper only requires one particular invocation of the binary operator and there is no `common_reference` requirement between any of the types involved.

Lastly, the `fold` here is proposed to go into `<algorithm>` rather than `<numeric>` since there is nothing especially numeric about it.

# Return Type

Consider the example:

```cpp
std::vector<double> v = {0.25, 0.75};
auto r = ranges::fold(v, 1, std::plus());
```

What is the type and value of `r`? There are two choices, which I'll demonstrate with implementations (with incomplete constraints).

## Always return `T`

We implement like so:

```cpp
template <range R, movable T, typename F>
auto fold(R&& r, T init, F op) -> T
{
    ranges::iterator_t<R> first = ranges::begin(r);
    ranges::sentinel_t<R> last = ranges::end(r);
    for (; first != last; ++first) {
        init = invoke(op, move(init), *first);
    }
    return init;
}
```

Here, `fold(v, 1, std::plus())` is an `int` because the initial value is `1`. Since our accumulator is an `int`, the result here is `1`. This is a consistent with `std::accumulate` and is simple to reason about and specify. But it is also a common gotcha with `std::accumulate`.

Note that if we use `assignable_from<T&, invoke_result_t<F&, T, range_reference_t<R>>>` as the constraint on this algorithm, in this example this becomes `assignable_from<int&, double>`. We would be violating the semantic requirements of `assignable_from`, which state [concept.assignable]{.sref}/1.5:

::: bq
[1.5]{.pnum} After evaluating `lhs = rhs`:

* [1.5.1]{.pnum} `lhs` is equal to `rcopy`, unless `rhs` is a non-const xvalue that refers to `lcopy`.
:::

This only holds if all the `double`s happen to be whole numbers, which is not the case for our example. This invocation would be violating the semantic constraints of the algorithm.

## Return the result of the initial invocation

When we talk about the mathematical definition of fold, that's `f(f(f(f(init, x1), x2), ...), xn)`. If we actually evaluate this expression in this context, that's `((1 + 0.25) + 0.75)` which would be `2.0`.

We cannot in general get this type correctly. A hypothetical `f` could actually change its type every time which we cannot possibly implement, so we can't exactly mirror the mathematical definition regardless. But let's just put that case aside as being fairly silly.

We could at least address the gotcha from `std::accumulate` by returning the decayed result of invoking the binary operation with `T` (the initial value) and the reference type of the range. That is, `U = decay_t<invoke_result_t<F&, T, ranges::range_reference_t<R>>>`. There are two possible approaches to implementing a fold that returns `U` instead of `T`:

::: cmptable
### Two invocation kinds
```cpp
template <range R, movable T, typename F,
            typename U = /* ... */>
auto fold(R&& r, T init, F f) -> U
{
    ranges::iterator_t<R> first = ranges::begin(r);
    ranges::sentinel_t<R> last = ranges::end(r);

    if (first == last) {
        return move(init);
    }

    U accum = invoke(f, move(init), *first);
    for (++first; first != last; ++first) {
        accum = invoke(f, move(accum), *first);
    }
    return accum;
}
```


### One invocation kind
```cpp
template <range R, movable T, typename F,
            typename U = /* ... */>
auto fold(R&& r, T init, F f) -> U
{
    ranges::iterator_t<R> first = ranges::begin(r);
    ranges::sentinel_t<R> last = ranges::end(r);

    U accum = std::move(init);
    for (; first != last; ++first) {
        accum = invoke(f, move(accum), *first);
    }
    return accum;
}
```
:::

Either way, our set of requirements is:

* `invocable<F&, T, range_reference_t<R>>` (even though the implementation on the right does not actually invoke the function using these arguments, we still need this to determine the type `U`)
* `invocable<F&, U, range_reference_t<R>>`
* `convertible_to<T, U>`
* `assignable_from<U&, invoke_result_t<F&, U, range_reference_t<R>>>`

While the left-hand side also needs `convertible_to<invoke_result_t<F&, T, range_reference_t<R>>, U>`.

This is a fairly complicated set of requirements.

But it means that our example, `fold(v, 1, std::plus())` yields the more likely expected result of `2.0`. So this is the version this paper proposes.

# Other `fold` algorithms

[@P2214R0] proposed a single fold algorithm that takes an initial value and a binary operation and performs a _left_ fold over the range. But there are a couple variants that are also quite valuable and that we should adopt as a family.

## `fold1`

Sometimes, there is no good choice for the initial value of the fold and you want to use the first element of the range. For instance, if I want to find the smallest string in a range, I can already do that as `ranges::min(r)` but the only way to express this in terms of `fold` is to manually pull out the first element, like so:

```cpp
auto b = ranges::begin(r);
auto e = ranges::end(r);
ranges::fold(ranges::next(b), e, *b, ranges::min);
```

But this is both tedious to write, and subtly wrong for input ranges anyway since if the `next(b)` is evaluated before `*b`, we have a dangling iterator. This comes up enough that this paper proposes a version of `fold` that uses the first element in the range as the initial value (and thus has a precondition that the range is not empty).

This algorithm exists in Scala and Kotlin (which call the non-initializer version `reduce` but the initializer version `fold`), Haskell (under the name `fold1`), and Rust (in the `Itertools` crate under the name `fold1` and recently finalized under the name `reduce` to match Scala and Kotlin [@iterator_fold_self], although at some point it was `fold_first`).

In Python, the single algorithm `functools.reduce` supports both forms (the `initializer` is an optional argument). In Julia, `foldl` and `foldr` both take an optional initial value as well (though it is mandatory in certain cases).

There are two questions to ask about the version of `fold` that does not take an extra initializer.

### Distinct name?

Should we give this algorithm a different name (e.g. `fold_first` or `fold1`, since `reduce` is clearly not an option for us) or provide it as an overload of `fold`? To answer that question, we have to deal with the question of ambiguity. For two arguments, `fold(xs, a)` can only be interpreted as a `fold` with no initial value using `a` as the binary operator. For four arguments, `fold(xs, a, b, c)` can only be interpreted as a `fold` with `a` as the initial value, `b` as the binary operation that is the reduction function, and `c` as a unary projection.

What about `fold(xs, a, b)`?  It could be:

1. Using `a` as the initial value and `b` as a binary reduction of the form `(A, X) -> A`.
2. Using `a` as a binary reduction of the form `(X, Y) -> X` and `b` as a unary projection of the form `X -> Y`.

Is it possible for these to collide? It would be an uncommon situation, since `b` would have to be both a unary and a binary function. But it is definitely _possible_:

```cpp
inline constexpr auto first = [](auto x, auto... ){ return x; };
auto r = fold(xs, first, first);
```

This call is ambiguous! This works with either interpretation. It would either just return `first` (the lambda) in the first case or the first element of the range in the second case, which makes it either completely useless or just mostly useless.

It's possible to force either the function or projection to ensure that it can only be interpreted one way or the other, but since the algorithm is sufficiently different (see following section), even if such ambiguity is going to be extremely rare (and possible to deal with even if it does arise), we may as well avoid the issue entirely.

As such, this paper proposes a differently named algorithm for the version that takes no initial value rather than adding an overload under the same name.

### `optional` or UB?

The result of `ranges::foldl(empty_range, init, f)` is just `init`. That is straightforward. But what would the result of `ranges::foldl1(empty_range, f)` be? There are two options:

1. a disengaged `optional<T>`, or
2. `T`, but this case is undefined behavior

In other words: empty range is either a valid input for the algorithm, whose result is `nullopt`, or there is a precondition that the range is non-empty.

Users can always recover the undefined behavior case if they want, by writing `*foldl1(empty_range, f)`, and the `optional` return allows for easy addition of other functionality, such as providing a sentinel value for the empty range case (`foldl1(empty_range, f).value_or(sentinel)` reads better than `not ranges::empty(r) ? foldl1(r, f) : sentinel`, at least to me). It's also much safer to use in the context where you may not know if the range is empty or not, because it's adapted: `foldl1(r | filter(f), op)`.

However, this would be the very first algorithm in the standard library that meaningful interacts with one of the sum types. And goes against the convention of algorithms simply being undefined for empty ranges (such as `max`). Although it's worth pointing out that `max_element` is _not_ UB for an empty range, it simply returns the end iterator, and the distinction there is likely due to simply not having had an available sentinel to return. But now we do.

This paper proposes returning `optional<T>`. Which is added motivation for a name distinct from the `fold` algorithm that takes an initializer.

## `fold_right`

While `ranges::fold` would be a left-fold, there is also occasionally the need for a _right_-fold. As with the previous section, we should also provide overloads of `fold_right` that do not take an initial value.

There are three questions that would need to be asked about `fold_right`.

First, the order of operations of to the function. Given `fold_right([1, 2, 3], z, f)`, is the evaluation `f(f(f(z, 3), 2), 1)` or is the evaluation `f(1, f(2, f(3, z)))`? Note that either way, we're choosing the `3` then `2` then `1`, both are right folds. It's a question of if the initial element is the left-hand operand (as it is in the left `fold`) or the right-hand operand (as it would be if consider the right fold as a flip of the left fold).

One advantage of the former - where the initial call is `f(z, 3)` - is that we can specify `fold_right(r, z, op)` as precisely `fold_left(views::reverse(r), z, op)` and leave it at that. Notably with the same `op`. With the latter - where the initial call is `f(3, z)` - we would need slightly more specification and would want to avoid saying `flip(op)` since directly invoking the operation with the arguments in the correct order is a little better in the case of ranges of prvalues.

If we take a look at how other languages handle left-fold and right-fold, and whether the accumulator is on the same side (and, in these cases, the accumulator is always on the right) or opposite side (the accumulator is on the left-hand side for left fold and on the right-hand side for right fold):

<table>
<tr><th>Same Side</th><th>Opposite Side</th></tr>
<tr><td>[Scheme](http://community.schemewiki.org/?fold)</td><td>[Haskell](https://wiki.haskell.org/Fold)</td></tr>
<tr><td>[Elixir](https://hexdocs.pm/elixir/List.html#foldl/3)</td><td>[F#](https://fsharp.github.io/fsharp-core-docs/reference/fsharp-collections-listmodule.html#fold)</td></tr>
<tr><td>[Elm](https://package.elm-lang.org/packages/elm/core/latest/List#foldl)</td><td>[Julia](https://docs.julialang.org/en/v1/base/collections/#Base.foldl-Tuple{Any,%20Any})</tr>
<tr><td /><td>[Kotlin](https://kotlinlang.org/api/latest/jvm/stdlib/kotlin.collections/)</td></tr>
<tr><td /><td>[OCaml](https://ocaml.org/api/List.html)</td></tr>
<tr><td /><td>[Scala](https://www.scala-lang.org/api/2.13.3/scala/collection/immutable/List.html)</td></tr>
</table>

This paper chooses what appears to be the more common approach: the accumulator is on the left-hand side for left fold and the right-hand side for right fold. That is, `foldr(r, z, op)` is equivalent to `foldl(reverse(r), z, flip(op))`.

Second, supporting bidirectional ranges is straightforward. Supporting forward ranges involves recursion of the size of the range. Supporting input ranges involves recursion and also copying the whole range first. Are either of these worth supporting? The paper simply supports bidirectional ranges.

Third, the naming question.

### Naming for left and right folds

There are roughly four different choices that we could make here:

1. Provide the algorithms `fold` (a left-fold) and `fold_right`.
2. Provide the algorithms `fold_left` and `fold_right`.
3. Provide the algorithms `fold_left` and `fold_right` and also provide an alias `fold` which is also `fold_left`.
4. Provide the algorithms `foldl` and `foldr`.

There's language precedents for any of these cases. F# and Kotlin both provide `fold` as a left-fold and suffixed right-fold (`foldBack` in F#, `foldRight` in Kotlin). Elm, Haskell, Julia, and OCaml provide symmetrically named algorithms (`foldl`/`foldr` for the first three and `fold_left`/`fold_right` for the third). Scala provides a `foldLeft` and `foldRight` while also providing `fold` to also mean `foldLeft`.

In C++, we don't have precedent in the library at this point for providing an alias for an algorithm, although we do have precedent in the library for providing an alias for a range adapter (`keys` and `values` for `elements<0>` and `elements<1>`, and [@P2321R0] proposes `pairwise` and `pairwise_transform` as aliases for `adjacent<2>` and `adjacent_transform<2>`). We also have precedent in the library for asymmetric names (`sort` vs `stable_sort` vs `partial_sort`) and symmetric ones (`shift_left` vs `shift_right`), even symmetric ones with terse names (`rotl` and `rotr`, although the latter are basically instructions).

All of which is to say, I don't think there's a clear answer to this question. There are, I think, three sane option banks:

|A|B|C|
|-|-|-|
|`fold_left`|`fold`|`foldl`|
|`fold_right`|`fold_right`|`foldr`|
|`fold_left_first`|`fold_first`|`foldl1`|
|`fold_right_first`|`fold_right_first`|`foldr1`|

And this paper proposes option C: `foldl` and `foldr`. It's the right mix of having symmetry between the two names, while also not making them too long. There is preference for `fold` over `fold_left` (both because it's more common than right-fold and thus having it shorter matters), and `foldl` is only a single character longer.

## Short-circuiting folds

The folds discussed up until now have always evaluated the entirety of the range. That's very useful in of itself, and several other algorithms that we have in the standard library can be implemented in terms of such a fold (e.g. `min` or `count_if`).

But for some algorithms, we really want to short circuit. For instance, we don't want to define `all_of(r, pred)` as `fold(r, true, logical_and(), pred)`. This formulation would give the correct answer, but we really don't want to keep evaluating `pred` once we got our first `false`. To do this correctly, we really need short circuiting.

There are (at least) three different approaches for how to have a short-circuiting fold. Here are different approaches to implementing `any_of` in terms of a short-circuiting fold:

1. You could provide a function that mutates the accumulator and returns `true` to continue and `false` to break. That is, `all_of(r, pred)` would look like

    ```cpp
    return fold_while(r, true, [&](bool& state, auto&& elem){
        state = pred(elem);
        return not state;
    });
    ```

    and the main loop of the `fold_while` algorithm would look like:

    ```cpp
    for (; first != last; ++first) {
        if (not f(init, *first)) { // NB: not moving init into "f"
            break;                 // since we're mutating in-place
        }
    }
    return init;
    ```

2. Same as #1, except return an enum class instead of a `bool` (like `control_flow::continue_` vs `control_flow::break_`).

3. You could provide a function that returns a `variant<continue_<T>, break_<U>>`. The algorithm would then return this variant (rather than a `T`). Rust's `Itertools` crate provides this under the name [`fold_while`](https://docs.rs/itertools/0.10.0/itertools/trait.Itertools.html#method.fold_while):

    ```cpp
    template <typename T> struct continue_ { T value; };

    template <typename T> struct break_ { T value; };
    template <> struct break_<void> { };
    break_() -> break_<void>;

    template <typename T, typename U>
    using fold_while_t = variant<continue_<T>, break_<U>>;

    return fold_while(r, true, [&](bool, auto&& elem) -> fold_while_t<bool, void> {
        if (pred(elem)) {
            return continue_{true};
        } else {
            return break_();
        }
    }).index() == 0;
    ```

    and the main loop of the `fold_while` algorithm would look like:

    ```cpp
    variant<continue_<T>, break_<E>> state = continue_<T>{init};

    for (; first != last; ++first) {
        state = f(get<continue_<T>>(move(state)).value, *first);
        if (holds_alternative<break_<U>>(next_state)) {
            break;
        }
    }
    return state;
    ```

4. You could provide a function that returns an `expected<T, E>`, which then the algorithm would return an `expected<T, E>` (rather than a `T`). Rust `Iterator` trait provides this under the name [`try_fold`](https://doc.rust-lang.org/std/iter/trait.Iterator.html#method.try_fold):

    ```cpp
    return fold_while(r, true, [&](bool, auto&& elem) -> expected<bool, bool> {
        if (pred(FWD(elem))) {
            return true;
        } else {
            return unexpected(false);
        }
    }).has_value();
    ```

    and the main loop of the `fold_while` algorithm would look like:

    ```cpp
    for (; first != last; ++first) {
        auto next = f(move(init), *first);
        if (not next) {
            return next;
        }
        init = *move(next);
    }

    return init;
    ```

Option (1) is a questionable option because of mutating state (note that we cannot use `predicate` as the constraint on the type, because `predicate`s are not allowed to mutate their arguments), but this approach is probably the most efficient due to not moving the accumulator at all.

Option (2) seems like a strictly worse version than Option (1) for C++, due to not being able to use existing predicates.

Option (3) is an awkward option for C++ because of general ergonomics. The provided lambda couldn't just return `continue_{x}` in one case and `break_{y}` in another since those have different types, so you'd basically always have to provide `-> fold_while_t<T, U>` as a trailing-return-type. This would also be the first (or second, see above) algorithm which actually meaningfully uses one of the standard library's sum types.

Option (4) isn't a great option for C++ because we don't even have `expected<T, E>` in the standard library yet (although hopefully imminent at this point, as [@P0323R10] is already being discussed in LWG), and ergonomically it has the same issues as described earlier - you can't just return a `T` and an `unexpected<E>` for a lambda, you need to have a trailing return type. We'd also want to generalize this approach to any "truthy" type which would require coming up with a way to conceptualize (in the `concept` sense) "truthy" (since `optional<T>` would be a valid type as well, as well as any other the various user-defined versions out there. Rust's name for this is `Try`, with a [new revision](https://rust-lang.github.io/rfcs/3058-try-trait-v2.html) in progress). Because the implementation would have to wrap and unwrap the accumulator, it could potentially be less efficient than Option (1) as well.

Or, to put these all in a table, given that the accumulator has type `T`:

<table>
<tr><th/><th>Callable is Pure?</th><th>Callable returns...</th><th>Algorithm returns...</th></tr>
<tr><th>1</th><td>❌</td><td>`bool`</td><td>`T`</td></tr>
<tr><th>2</th><td>❌</td><td>`enum class control_flow`</td><td>`T`</td></tr>
<tr><th>3</th><td>✔️</td><td>`variant<continue_<T>, break_<U>>`</td><td>`variant<continue_<T>, break_<U>>`</td></tr>
<tr><th>4</th><td>✔️</td><td>`expected<T, E>`<br/>`optional<T>`</td><td>`expected<T, E>`<br />`optional<T>`</td></tr>
</table>

Option (3) is far too unergonomic in C++ to be reasonable, but Option (4) does have the benefit that it would allow different return types for the early-return and full-consume cases.

None of these options stand out as particularly promising. Moreover, I've been unable to find any other other than Rust which provides such an algorithm (even though basically every language provides algorithms that reduce to a short-circuiting fold, like `any` and `all`), and in Rust, this algorithm is quite ergonomic due to language features that C++ does not possess. As such, while a previous revision of this paper proposed a short-circuiting fold (specifically, Option 1), this paper does not.

## Iterator-returning folds

Up until this point, this paper has only discussed returning a _value_ from `fold`: whatever we get as the result of `f(f(f(f(init, e0), e1), e2), e3)`. But there is another value that we compute along the way that is thrown out: the end iterator.

An alternative formulation of `fold` would preserve that information. Rather than returning `R`, we could do something like this:

```cpp
template <input_iterator I, typename R>
struct fold_result {
    I in;
    R value;
};

template <input_iterator I, sentinel_for<I> S, class T, class Proj = identity,
    @*indirectly-binary-left-foldable*@<T, projected<I, Proj>> F,
    typename R = invoke_result_t<F&, T, indirect_result_t<Proj&, I>>>
constexpr auto foldl(I first, S last, T init, F f, Proj proj = {})
    -> fold_result<I, R>;
```

But the problem with that direction is, quoting from [@P2214R0]:

::: quote
[T]he above definition definitely follows Alexander Stepanov's law of useful return [@stepanov] (emphasis ours):

::: quote
When writing code, it’s often the case that you end up computing a value that the calling function doesn’t currently need. Later, however, this value may be important when the code is called in a different situation. In this situation, you should obey the law of useful return: *A procedure should return all the potentially useful information it computed.*
:::

But it makes the usage of the algorithm quite cumbersome. The point of a fold is to return the single value. We would just want to write:

```cpp
int total = ranges::sum(numbers);
```

Rather than:

```cpp
auto [_, total] = ranges::sum(numbers);
```

or:

```cpp
int total = ranges::sum(numbers, 0).value;
```

`ranges::fold` should just return `T`. This would be consistent with what the other range-based folds already return in C++20 (e.g. `ranges::count` returns a `range_difference_t<R>`, `ranges::any_of` - which can't quite be a `fold` due to wanting to short-circuit - just returns `bool`).
:::

Moreover, even if we added a version of this algorithm that returned an iterator (let's call it `fold_with_iterator`), we wouldn't want `fold(first, last, init, f)` to be defined as
```cpp
return fold_with_iterator(first, last, init, f).value;
```
since this would have to incur an extra move of the accumulated result, due to lack of copy elision (we have different return types). So we'd want need this algorithm to be specified separately (or, perhaps, the "*Effects*: equivalent to" formulation is sufficiently permissive as to allow implementations to do the right thing?)

From a usability perspective, I think it's important that `fold` just return the value.

The problem going past that is that we end up with this combinatorial explosion of algorithms based on a lot of orthogonal choices:

1. iterator pair or range
2. left or right fold
3. initial value or no initial value
4. short-circuit or not short-circuit
5. return `T` or `(iterator, T)`

Which would be... 32 distinct functions (under 16 different names) if we go all out. And these really are basically orthogonal choices. Indeed, a short-circuiting fold seems even more likely to want the iterator that the algorithm stopped at! Do we need to provide all of them? Maybe we do!

This brings with it its own naming problem. That's a lot of names. One approach there could be a suffix system:

* `foldl` is a non-short-circuiting left-fold with an initial value that returns `T`
* `foldl1` is a non-short-circuiting left-fold with no initial value that returns `T`
* `foldl1_while` is a short-circuiting left-fold with no initial value that returns `T`
* `foldr_with_iter` is a non-short-circuiting right-fold with an initial value that returns `(iterator, T)`
* `foldr1_while_with_iter` is a short-circuiting right-fold with no initial value that returns `(iterator, T)`

`with_iter` is not the best suffix, but the rest seem to work out ok.

## The proposal: iterator-returning left folds

One solution to the combinatorial explosion problem, as suggested by Tristan Brindle, is to simply not consider all of these options as being necessarily orthogonal. That is, providing a left-fold that returns a value is very valuable and highly desired. But having both a left- and right-fold that return an iterator?

In other words, if you want the common and convenient thing, we'll provide that: `foldl` and `foldl1` will exist and just return a value. But if you want a more complex tool, it'll be a little more complicated to use. In other words, what this paper is proposing is six algorithms (with two overloads each):

1. `foldl` (a left-fold with an initial value that returns `T`)
2. `foldl1` (a left-fold with no initial value that returns `T`)
3. `foldr` (a right-fold with an initial value that returns `T`)
4. `foldr1` (a right-fold with no initial value that returns `T`)
5. `foldl_with_iter` (a left-fold with an initial value that returns `(iterator, T)`)
6. `foldl1_with_iter` (a left-fold with no initial value that returns `(iterator, T)`)

There is no right-fold that returns an iterator, since you can use `views::reverse`. This is a little harder to use since the transition from a fold that just returns `T` to a fold that actually produces an `iterator` as well isn't as easy as going from:

::: bq
```cpp
auto value = ranges::foldl(r, init, op);
```
:::

to:

::: bq
```cpp
auto [iterator, value] = ranges::foldl_with_iter(r, init, op);
```
:::

Instead, you have to flip the binary operation - and we have no `flip` function adapter ([Boost.HOF](https://www.boost.org/doc/libs/1_77_0/libs/hof/doc/html/include/boost/hof/flip.html) does though).

## No projections

All the algorithms in `std::ranges` take a projection, but there's a problem in this case. For `foldl`, there's no problem - we just look over the iterators and do `invoke(proj, *first)` before passing that into the call to `f`.

But for `foldl1`, we need to produce an initial _value_, rather than an initial _reference_. And with a projection, we can't... do that for iterators that give proxy references. Let's start by writing out what `foldl1` would be implemented as, without a projection, and then try to add it in:

::: bq
```cpp
template <input_iterator I, sentinel_for<I> S,
  indirectly-binary-left-foldable<iter_value_t<I>, I> F>
  requires constructible_from<iter_value_t<I>, iter_reference_t<I>>
constexpr auto foldl1(I first, S last, F f) {
  using U = decltype(ranges::foldl(first, last, iter_value_t<I>(*first), f));
  if (first == last) {
    return optional<U>(nullopt);
  }

  iter_value_t<I> init(*first); // <==
  ++first;
  return optional<U>(in_place,
    ranges::foldl(std::move(first), std::move(last), std::move(init), std::move(f)));
}
```
:::

Now, how do we replace the commented line with a projected version of the same? We need a *value*. Imagine if `*first` yielded a `tuple<T&>` (as it does for `zip`) and our projection is `identity` (the common case). If we did:

::: bq
```cpp
iter_value_t<projected<I, Proj>> init(invoke(proj, *first));
```
:::

We'd still end up with a `tuple<T&>`, whereas we'd need to end up with a `tuple<T>`. The only way to get this right is to project the value type first:

::: bq
```cpp
auto init = invoke(proj, iter_value_t<I>(*first));
```
:::

But that's not actually required to be valid. The projection is required to take either `iter_reference_t<I>` or `iter_value_t<I>&` (specifically an _lvalue_ of the value type). So you _have_ to write this:

::: bq
```cpp
iter_value_t<I> init_(*first);
optional<U> init(in_place, invoke(proj, init_));
```
:::

Which means that the only way to get this right is to incur an extra copy.

Which means we're performing an extra copy in the typical case (the iterator does not yield a proxy reference and there is no projection) simply to be able to support the rare case. That seems problematic. And we don't have any other algorithm where we'd need to get a projected _value_, we only ever need projected _references_ (algorithms like `min` which return a value type return the value type of the original range, not the projected range).

This suggests dropping the projections for the `*1` variants (`foldl1`, `foldr1`, and `fold1_with_iter`). But then they're more inconsistent with the other variants, so this paper suggests simply not having projections at all. This doesn't cost you anything for some of the algorithms, since projections in these case can always be provided either as range adaptors or function adaptors.

The expression that I'm not supporting:

::: bq
```cpp
foldl(r, init, f, proj)
```
:::

means the same as either this version using a range adaptor:

::: bq
```cpp
foldl(r | views::transform(proj), init, f)
```
:::

or this version using a function adaptor (Boost.HOF defines an adaptor `proj` such that `proj(p, f)(xs...)` means `f(p(xs)...)`. We need to project only the right hand argument, so here `proj_rhs(p, f)(x, y)` means `f(x, p(y))` as desired)

::: bq
```cpp
foldl(r, init, proj_rhs(proj, f))
```
:::

The version using `views::transform` is probably more familiar, but it won't work as well for `foldl_with_iter` since this would return `dangling` (since `transform` is never a borrowed range) but even with adjustment would return an iterator into the transformed range rather than the original range. This issue is one of the original cited motivations for projections in [@N4128]. The version using the function adaptor has no such issue, although proposing more function adaptors into the standard library is out of scope for this paper.

In short, there are good reasons to avoid projections for `foldl1`, `foldr1`, and `foldl1_with_iter`. For consistency, I'm also removing the projections for `foldl`, `foldr`, and `foldl_with_iter`. This makes the folds inconsistent with the rest of the standard library algorithms (although at least internally consistent), but it doesn't actually cost them functionality.

# Implementation Experience

Part of this paper (containing the algorithms `foldl`, `foldl1`, `foldr`, and `foldr1`, where the `*1` algorithms return an `optional`) has been implemented in range-v3 [@range-v3-fold] (with projections, although not quite correctly as it turns out).

The algorithms returning an iterator have not been implemented in range-v3 yet, but they're exactly the same as their non-iterator-returning counterparts.

# Wording

Append to [algorithm.syn]{.sref}, first a new result type:

::: bq
```diff
#include <initializer_list>

namespace std {
  namespace ranges {
    // [algorithms.results], algorithm result types
    template<class I, class F>
      struct in_fun_result;

    template<class I1, class I2>
      struct in_in_result;

    template<class I, class O>
      struct in_out_result;

    template<class I1, class I2, class O>
      struct in_in_out_result;

    template<class I, class O1, class O2>
      struct in_out_out_result;

    template<class T>
      struct min_max_result;

    template<class I>
      struct in_found_result;

+   template<class I, class T>
+     struct in_value_result;
  }

  // ...
}
```
:::

and then also a bunch of fold algorithms:

::: bq
```cpp
namespace std {
  // ...

  // [alg.fold], folds
  namespace ranges {
    template<class F>
    struct @*flipped*@ {  // exposition only
      F f;

      template<class T, class U>
        requires invocable<F&, U, T>
      invoke_result_t<F&, U, T> operator()(T&&, U&&);
    };

    template <class F, class T, class I, class U>
    concept @*indirectly-binary-left-foldable-impl*@ =  // exposition only
        movable<T> &&
        movable<U> &&
        convertible_to<T, U> &&
        invocable<F&, U, iter_reference_t<I>> &&
        assignable_from<U&, invoke_result_t<F&, U, iter_reference_t<I>>>;

    template <class F, class T, class I>
    concept @*indirectly-binary-left-foldable*@ =      // exposition only
        copy_constructible<F> &&
        indirectly_readable<I> &&
        invocable<F&, T, iter_reference_t<I>> &&
        convertible_to<invoke_result_t<F&, T, iter_reference_t<I>>,
               decay_t<invoke_result_t<F&, T, iter_reference_t<I>>>> &&
        @*indirectly-binary-left-foldable-impl*@<F, T, I, decay_t<invoke_result_t<F&, T, iter_reference_t<I>>>>;

    template <class F, class T, class I>
    concept @*indirectly-binary-right-foldable*@ =    // exposition only
        @*indirectly-binary-left-foldable*@<@*flipped*@<F>, T, I>;

    template<input_iterator I, sentinel_for<I> S, class T
      @*indirectly-binary-left-foldable*@<T, I> F>
    constexpr auto foldl(I first, S last, T init, F f);

    template<input_range R, class T,
      @*indirectly-binary-left-foldable*@<T, iterator_t<R>> F>
    constexpr auto foldl(R&& r, T init, F f);

    template <input_iterator I, sentinel_for<I> S,
      @*indirectly-binary-left-foldable*@<iter_value_t<I>, I> F>
      requires constructible_from<iter_value_t<I>, iter_reference_t<I>>
    constexpr auto foldl1(I first, S last, F f);

    template <input_range R,
      @*indirectly-binary-left-foldable*@<range_value_t<R>, iterator_t<R>> F>
      requires constructible_from<range_value_t<R>, range_reference_t<R>>
    constexpr auto foldl1(R&& r, F f);

    template<bidirectional_iterator I, sentinel_for<I> S, class T,
      @*indirectly-binary-right-foldable*@<T, I> F>
    constexpr auto foldr(I first, S last, T init, F f);

    template<bidirectional_range R, class T,
      @*indirectly-binary-right-foldable*@<T, iterator_t<R>> F>
    constexpr auto foldr(R&& r, T init, F f);

    template <bidirectional_iterator I, sentinel_for<I> S,
      @*indirectly-binary-right-foldable*@<iter_value_t<I>, I> F>
      requires constructible_from<iter_value_t<I>, iter_reference_t<I>>
    constexpr auto foldr1(I first, S last, F f);

    template <bidirectional_range R,
      @*indirectly-binary-right-foldable*@<range_value_t<R>, iterator_t<R>> F>
      requires constructible_from<range_value_t<R>, range_reference_t<R>>
    constexpr auto foldr1(R&& r, F f);

    template<class I, class T>
      using foldl_with_iter_result = in_value_result<I, T>;
    template<class I, class T>
      using foldl1_with_iter_result = in_value_result<I, T>;

    template<input_iterator I, sentinel_for<I> S, class T,
       @*indirectly-binary-left-foldable*@<T, I> F>
    constexpr $see below$ foldl_with_iter(I first, S last, T init, F f);

    template<input_range R, class T,
      @*indirectly-binary-left-foldable*@<T, iterator_t<R>> F>
    constexpr $see below$ foldl_with_iter(R&& r, T init, F f);

    template <input_iterator I, sentinel_for<I> S,
      @*indirectly-binary-left-foldable*@<iter_value_t<I>, I> F>
      requires constructible_from<iter_value_t<I>, iter_reference_t<I>>
    constexpr $see below$ foldl1_with_iter(I first, S last, F f);

    template <input_range R,
      @*indirectly-binary-left-foldable*@<range_value_t<R>, iterator_t<R>> F>
      requires constructible_from<range_value_t<R>, range_reference_t<R>>
    constexpr $see below$ foldl1_with_iter(R&& r, F f);
  }
}
```
:::

Add a new result type to [algorithms.results]{.sref}:

::: bq
```diff
namespace std::ranges {
  // ...

  template<class I>
  struct in_found_result {
    [[no_unique_address]] I in;
    bool found;

    template<class I2>
      requires convertible_­to<const I&, I2>
    constexpr operator in_found_result<I2>() const & {
      return {in, found};
    }
    template<class I2>
      requires convertible_­to<I, I2>
    constexpr operator in_found_result<I2>() && {
      return {std::move(in), found};
    }
  };

+ template<class I, class T>
+ struct in_value_result {
+   [[no_unique_address]] I in;
+   [[no_unique_address]] T value;
+
+   template<class I2, class T2>
+     requires convertible_to<const I&, I2> && convertible_to<const T&, T2>
+   constexpr operator in_value_result<I2, T2>() const & {
+     return {in, value};
+   }
+
+   template<class I2, class T2>
+     requires convertible_to<I, I2> && convertible_to<T, T2>
+   constexpr operator in_value_result<I2, T2>() && {
+     return {std::move(in), std::move(value)};
+   }
+ };
}
```
:::

And add a new clause, [alg.fold]:

::: bq
```cpp
template<input_iterator I, sentinel_for<I> S, class T,
  @*indirectly-binary-left-foldable*@<T, I> F>
constexpr auto ranges::foldl(I first, S last, T init, F f);

template<input_range R, class T,
  @*indirectly-binary-left-foldable*@<T, iterator_t<R>> F>
constexpr auto ranges::foldl(R&& r, T init, F f);
```

[#]{.pnum} *Returns*: `ranges::foldl_with_iter(std::move(first), last, std::move(init), f).value`

```cpp
template <input_iterator I, sentinel_for<I> S,
  @*indirectly-binary-left-foldable*@<iter_value_t<I>, I> F>
  requires constructible_from<iter_value_t<I>, iter_reference_t<I>>
constexpr auto ranges::foldl1(I first, S last, F f);

template <input_range R,
  @*indirectly-binary-left-foldable*@<range_value_t<R>, iterator_t<R>> F>
  requires constructible_from<range_value_t<R>, range_reference_t<R>>
constexpr auto ranges::foldl1(R&& r, F f);
```

[#]{.pnum} *Returns*: `ranges::foldl1_with_iter(std::move(first), last, f).value`


```cpp
template<bidirectional_iterator I, sentinel_for<I> S, class T,
  @*indirectly-binary-right-foldable*@<T, I> F>
constexpr auto ranges::foldr(I first, S last, T init, F f);

template<bidirectional_range R, class T,
  @*indirectly-binary-right-foldable*@<T, iterator_t<R>> F>
constexpr auto ranges::foldr(R&& r, T init, F f);
```

[4]{.pnum} *Effects*: Equivalent to:

::: bq
```cpp
using U = decay_t<invoke_result_t<F&, iter_reference_t<I>, T>>;

if (first == last) {
    return U(std::move(init));
}

I tail = ranges::next(first, last);
U accum = invoke(f, *--tail, std::move(init));
while (first != tail) {
    accum = invoke(f, *--tail, std::move(accum));
}
return accum;
```
:::

```cpp
template <bidirectional_iterator I, sentinel_for<I> S,
  @*indirectly-binary-right-foldable*@<iter_value_t<I>, I> F>
  requires constructible_from<iter_value_t<I>, iter_reference_t<I>>
constexpr auto ranges::foldr1(I first, S last, F f);

template <bidirectional_range R,
  @*indirectly-binary-right-foldable*@<range_value_t<R>, iterator_t<R>> F>
  requires constructible_from<range_value_t<R>, range_reference_t<R>>
constexpr auto ranges::foldr1(R&& r, F f);
```

[#]{.pnum} Let `U` be `decltype(ranges::foldr(first, last, iter_value_t<I>(*first), f))`.

[#]{.pnum} *Effects*: Equivalent to:

::: bq
```cpp
if (first == last) {
    return optional<U>();
}

I tail = ranges::prev(ranges::next(first, std::move(last)));
return optional<U>(in_place,
    ranges::foldr(std::move(first), tail, iter_value_t<I>(*tail), std::move(f)));
```
:::

```cpp
template<input_iterator I, sentinel_for<I> S, class T,
  @*indirectly-binary-left-foldable*@<T, I> F>
constexpr $see below$ foldl_with_iter(I first, S last, T init, F f);

template<input_range R, class T,
  @*indirectly-binary-left-foldable*@<T, iterator_t<R>> F>
constexpr $see below$ foldl_with_iter(R&& r, T init, F f);
```

[#]{.pnum} Let `U` be `decay_t<invoke_result_t<F&, T, iter_reference_t<I>>>`

[#]{.pnum} *Effects*: Equivalent to:

::: bq
```cpp
if (first == last) {
    return {std::move(first), U(std::move(init))};
}

U accum = invoke(f, std::move(init), *first);
for (++first; first != last; ++first) {
    accum = invoke(f, std::move(accum), *first);
}
return {std::move(first), std::move(accum)};
```
:::

[#]{.pnum} *Remarks*: The return type is `foldl_with_iter_result<I, U>` for the first overload and `foldl_with_iter_result<borrowed_iterator_t<R>, U>` for the second overload.

```cpp
template <input_iterator I, sentinel_for<I> S,
  @*indirectly-binary-left-foldable*@<iter_value_t<I>, I> F>
  requires constructible_from<iter_value_t<I>, iter_reference_t<I>>
constexpr $see below$ foldl1_with_iter(I first, last, F f)

template <input_range R,
  @*indirectly-binary-left-foldable*@<range_value_t<R>, iterator_t<R>> F>
  requires constructible_from<range_value_t<R>, range_reference_t<R>>
constexpr $see below$ foldl1_with_iter(R&& r, F f);
```

[#]{.pnum} Let `U` be `decltype(ranges::foldl(std::move(first), last, iter_value_t<I>(*first), f))`.

[#]{.pnum} *Effects*: Equivalent to:

::: bq
```cpp
if (first == last) {
    return {std::move(first), optional<U>()};
}

optional<U> init(in_place, *first);
for (++first; first != last; ++first) {
    *init = invoke(f, std::move(*init), *first);
}
return {std::move(first), std::move(init)};
```
:::

[#]{.pnum} *Remarks*: The return type is `foldl1_with_iter_result<I, optional<U>>` for the first overload and `foldl1_with_iter_result<borrowed_iterator_t<R>, optional<U>>` for the second overload.


:::

---
references:
    - id: iterator_fold_self
      citation-label: iterator_fold_self
      title: " Tracking issue for `iterator_fold_self`"
      author:
        - family: Ashley Mannix
      issued:
        year: 2020
      URL: https://github.com/rust-lang/rust/issues/68125
    - id: stepanov
      citation-label: stepanov
      title: From Mathematics to Generic Programming
      author:
        - family: Alexander A. Stepanov
      issued:
        year: 2014
    - id: P2322-minutes
      citation-label: P2322-minutes
      title: "P2322 Minutes"
      author:
        - family: LEWG
      issued:
        year: 2021
      URL: https://wiki.edg.com/bin/view/Wg21telecons2021/P2322#2021-05-03
    - id: range-v3-fold
      citation-label: range-v3-fold
      title: "Fold algos"
      author:
        - family: Barry Revzin
      issued:
        year: 2021
      URL: https://github.com/ericniebler/range-v3/pull/1628
---
