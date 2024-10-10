def create_sample_data():
    logger.info("Creating sample data...")
    try:
        # Check if properties already exist
        cbm = Property.query.filter_by(name="CBM").first()
        if cbm is None:
            # If CBM doesn't exist, create all sample data
            cbc = Property(name="CBC", description="Log Cabin, Pavilion, Deerfield, Kurth Annex, Kurth House")
            cbm = Property(name="CBM", description="Firemeadow, Sunday House")
            db.session.add_all([cbc, cbm])
            db.session.commit()

            cbc_units = [
                Unit(name="Log Cabin", property_id=cbc.id),
                Unit(name="Pavilion", property_id=cbc.id),
                Unit(name="Deerfield", property_id=cbc.id),
                Unit(name="Kurth Annex", property_id=cbc.id),
                Unit(name="Kurth House", property_id=cbc.id)
            ]
            cbm_units = [
                Unit(name="Firemeadow - Main Lodge", property_id=cbm.id),
                Unit(name="Firemeadow - Cabin 0", property_id=cbm.id),
                Unit(name="Firemeadow - Cabin 1", property_id=cbm.id),
                Unit(name="Firemeadow - Cabin 2", property_id=cbm.id),
                Unit(name="Firemeadow - Cabin 3", property_id=cbm.id),
                Unit(name="Firemeadow - Cabin 4", property_id=cbm.id),
                Unit(name="Firemeadow - Cabin 5", property_id=cbm.id),
                Unit(name="Firemeadow - Cabin 6", property_id=cbm.id),
                Unit(name="Firemeadow - Meadowlark", property_id=cbm.id),
                Unit(name="Firemeadow - Mariposa", property_id=cbm.id),
                Unit(name="Firemeadow - Magnolia", property_id=cbm.id),
                Unit(name="Firemeadow - Pinehurst", property_id=cbm.id),
                Unit(name="Firemeadow - Montgomery", property_id=cbm.id),
                Unit(name="Firemeadow - ALL", property_id=cbm.id),
                Unit(name="Sunday House", property_id=cbm.id)
            ]
            db.session.add_all(cbc_units + cbm_units)
            db.session.commit()

            admin_user = User(username='admin')
            admin_user.set_password(app.config['ADMIN_PASSPHRASE'])
            regular_user = User(username='user')
            regular_user.set_password(app.config['USER_PASSPHRASE'])
            db.session.add_all([admin_user, regular_user])
            db.session.commit()

            logger.info("Sample data created successfully")
        else:
            # If CBM exists, just add the new unit if it doesn't exist
            new_unit = Unit.query.filter_by(name="Firemeadow - ALL", property_id=cbm.id).first()
            if new_unit is None:
                new_unit = Unit(name="Firemeadow - ALL", property_id=cbm.id)
                db.session.add(new_unit)
                db.session.commit()
                logger.info("Added new unit 'Firemeadow - ALL' to CBM property")
            else:
                logger.info("Unit 'Firemeadow - ALL' already exists in CBM property")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating sample data: {str(e)}")

# Keep the rest of the file unchanged
