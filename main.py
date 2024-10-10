# Add this route after the existing routes
@app.route('/get_units/<int:property_id>')
@login_required
def get_units(property_id):
    units = Unit.query.filter_by(property_id=property_id).all()
    return jsonify([{'id': unit.id, 'name': unit.name} for unit in units])

# Keep the rest of the file unchanged
