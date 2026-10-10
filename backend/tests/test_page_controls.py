from backend.page_controls import summarize_controls


def test_form_summary_includes_real_control_names_without_values():
    html = """
    <label for="username">Username</label>
    <input id="username" name="username" type="text" value="student">
    <label for="password">Password</label>
    <input id="password" name="password" type="password" value="Password123">
    <button id="submit">Submit</button>
    """

    summary = summarize_controls(html)

    assert "label=Username" in summary
    assert "label=Password" in summary
    assert "id=submit" in summary
    assert "text=Submit" in summary
    assert "Password123" not in summary
    assert "student" not in summary
