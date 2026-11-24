# Blocked / diagnostic configs

These configs are deliberately outside the `wsc/oracle/*.json` glob that
`make -C wsc gb-oracle` runs. They are the C24 SHMUP investigation, not
passing acceptance configs.

- `shmup.json` is the intended full Space Battle comparison (movement in both
  axes, screen clamps, auto-scroll, enemy scripts and projectiles, all SHMUP
  state globals). It diverges at tick 1 because `shooter_dest` is
  `image_width - SCREEN_WIDTH_HALF`, and the WSC half-width is 112 px while
  the GB half-width is 80 px.
- `shmup-actors.json` is the same route without `shooter_dest`, to show the
  next viewport effect: enemy `actor[2]` activates on WSC at tick 74 and on
  GB at tick 98, so its update script has moved it by the time GB activates
  it (first divergence tick 98, `actor[2].y`).
- `shmup-projectiles.json` compares only player state and the active
  projectile list. It shows the same viewport effect through projectile
  firing/culling: WSC has one active projectile at tick 109 while GB has
  none.
- `shmup-player.json` compares only player state (no `shooter_dest`, actor
  or projectile fields). The next divergence is `player_iframes` at tick 513
  (GB 20, WSC 0): an enemy collision happens on only one side because the
  enemies are already at different positions.
- `shmup-short.json` stops at tick 60, before the first viewport-caused
  activation, and omits `shooter_dest`. It matches and is used only for the
  break/restore check of `shooter_scroll_speed`.

The common root cause and the open design question (keep the wider WSC
playfield, or give SHMUP a GB-width logical viewport for movement, activation
and projectile culling) are written up in
`.agent/reports/C24-shmup-pnc-report.md`.
