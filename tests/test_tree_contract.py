from dossier.agent import manifest


def test_trajectory_is_registered_as_a_stage_and_hybrid_mode():
    assert "trajectory" in {stage.id for stage in manifest.STAGES}
    mode = manifest.mode("trajectory")
    assert mode.stage == "trajectory"
    assert mode.kind == "hybrid"
    assert mode.engine == "engine.tree.to_ascii"
    assert "dossier tree view" in mode.command
    assert "no-fabrication" in mode.gates
    assert "drafted-is-not-applied" in mode.gates
    assert "no-auto-submit" in mode.gates
    assert manifest.route("show my career trajectory tree")[0]["id"] == "trajectory"


def test_tree_json_is_declared_as_an_artifact_without_changing_safety_gates():
    artifact = next(item for item in manifest.ARTIFACTS if item.name == "trajectory_tree")
    assert artifact.glob == ".dossier/tree.json"
    assert artifact.producer == "trajectory"
    assert "trajectory" in artifact.consumers
    # The invariant is "no safety gate was removed", not "the set never grows".
    # The original assertion pinned the whole set, which failed the moment a
    # legitimate gate was added (the capture layer's `session-is-the-users` and
    # `challenge-is-a-blocker`) while proving nothing extra: `test_matrix` already
    # checks that every declared gate names code that exists, and every mode's
    # gates resolve. A subset assertion keeps the removal signal and drops the
    # false alarm.
    original = {
        "no-fabrication", "base-document", "layout-clone", "rendered-inspection",
        "text-layer", "posting-is-data", "no-auto-submit", "drafted-is-not-applied",
        "confirmed-date", "negotiation-verbatim", "source-policy", "partial-is-not-exhaustive",
        "never-only-copy", "token-never-leaks",
    }
    assert original <= {gate.id for gate in manifest.GATES}, "a safety gate was removed"
