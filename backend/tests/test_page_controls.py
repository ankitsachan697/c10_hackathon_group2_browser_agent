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


def test_discovery_includes_late_checkout_controls_without_field_values():
    html = ''.join(f'<button>Navigate {i}</button>' for i in range(16))
    html += '<label for="address">Shipping address</label><input id="address" value="private"><button>Place order</button>'
    summary = summarize_controls(html)
    assert 'label=Shipping address' in summary and 'text=Place order' in summary
    assert 'private' not in summary and len(summary) <= 3200
