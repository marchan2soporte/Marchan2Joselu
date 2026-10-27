import cash_register

def open_test_cash(store):
    if not cash_register.status(store):
        cash_register.mutate(store,'cash_open',{'opening':'0','request_id':'fixture-opening'},1)
