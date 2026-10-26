# Wrap-up mode

`Wrap up` means drain what is already in flight without widening the session's work set. It is
not an instruction to cancel agents, abandon cards, or rush a card through its gates.

## Boundary at the moment of the command

The wrap-up set contains:

- every card already active in Design or Build for this identity; and
- every Review card whose reviewer has already been dispatched.

Keep those cards through their normal verification, reporting, tracker transitions, git
integration, and worktree release. Do not return them or move them early merely to end sooner.

Do not claim any Queue card, even when `wip.free > 0`. Do not dispatch a review that was not
already running when `Wrap up` arrived. In particular, a build that reaches Review during
wrap-up stays there for a later session.

## Recovery and tracker calls

Recovery may preserve the set but never widen it:

- Relaunch an agent that crashed while already working a wrap-up card.
- If an already-running review returns `needs_work`, the same card may be resumed and brought
  back to Review, but do not start another review round during wrap-up.
- `next_task` may be used to locate or resume a card already in the wrap-up set. Ignore newly
  offered Queue or Review cards: do not claim, dispatch, or add them to the set.

## Completion

When no wrap-up card or reviewer remains active, report what finished and what remains in Review
or blocked for later. Do not call `ScheduleWakeup` or begin another drain tick. Stop or cancel an
interval-backed loop through the host's loop control when available. If a queued wake fires before
cancellation takes effect, remain in drain-only mode and take no new work.

The mode remains active until the human explicitly tells the session to resume intake. Free
slots, newly available cards, later ticks, or an empty current set do not cancel it implicitly.
