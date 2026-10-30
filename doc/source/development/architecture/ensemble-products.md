# Interpreting existing ensemble products

The GRIB statistics path interprets a supplied result field. It does not load
individual members to calculate a mean, standard deviation, or replacement
product.

An effective ensemble definition must identify its object parameter, operation,
product-local population, and required method. The catalog population specifies
member identities and an explicit missing-member policy. Member ranges observed
in an original forecast archive do not establish the population of a separately
published result.

For the finite master-table-4/local-table-0 path, PDT 4.2 describes a derived
instantaneous object and PDT 4.12 preserves the object's time statistic and
actual interval. Neither generates an individual member identity. An ensemble
result cannot be selected as member zero or reinterpreted as a control forecast.

The supported derived-forecast codes include 0 for an unweighted mean, 4 for
spread when the concrete definition independently establishes standard deviation
and its method, and the existing minimum/maximum paths. Code 4 alone does not
determine the standard-deviation denominator. The fixed definition must provide
weighting and `ddof`; cluster deviations, normalized cluster deviations, weighted
means, variance, and local-use codes retain their separate unsupported paths.
These rules do not assert any operational CMA product or production algorithm.

When the native result provides a forecast count, the interpreter checks it
against the declared population size and missing policy. `require_all` requires
the full count; `use_available` requires a count between the explicit minimum
and population size. An absent count or the GRIB missing marker leaves the
explicit product population in force. A count does not establish member
identities or prove whether a control member participated. Zero is invalid for
this derived-result count; existing individual REPS member metadata containing
zero is handled by its separate member path.

Tests use generated result fields with explicit synthetic populations and
methods, including both supported template families. They verify selection,
assembly, units, intervals, diagnostics, and absence of member identities.
Operational binding and numerical acceptance still require an actual published
result and its product, population, method, time, and unit evidence. Current
GEPS/REPS builtin registrations continue to describe the reviewed original
member products; they do not acquire a formal statistical-product binding from
this mechanism alone.
