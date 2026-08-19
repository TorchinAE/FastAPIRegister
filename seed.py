"""Seed script — заполняет БД тестовыми данными."""
import asyncio
from scr.dbase.database import db_helper
from scr.dbase.models import (
    User, Positions, Directors, Organization, Counterparty, Request, RequestStatus,
)
from scr.dbase.crud_users import hash_password


async def seed():
    async with db_helper.session_factory() as session:
        # --- Users ---
        user1 = User(name="Иванов Иван Иванович", email="ivan@test.ru", hashed_password=hash_password("123456"), city="мск")
        user2 = User(name="Петрова Мария Сергеевна", email="maria@test.ru", hashed_password=hash_password("123456"), city="спб")
        user3 = User(name="Сидоров Алексей Петрович", email="sidorov@company.ru", hashed_password=hash_password("123456"), city="екб")
        session.add_all([user1, user2, user3])
        await session.flush()

        # --- Positions ---
        pos1 = Positions(name="Директор", created_by="Иванов И.И.")
        pos2 = Positions(name="Генеральный директор", created_by="Иванов И.И.")
        pos3 = Positions(name="Финансовый директор", created_by="Иванов И.И.")
        pos4 = Positions(name="Коммерческий директор", created_by="Мария П.")
        session.add_all([pos1, pos2, pos3, pos4])
        await session.flush()

        # --- Directors ---
        dir1 = Directors(name="Волков Андрей Николаевич", email="volkov@dir.ru", phone="+79101234567", position_id=pos2.id, created_by="Иванов И.И.")
        dir2 = Directors(name="Соколова Ольга Дмитриевна", email="sokolova@dir.ru", phone="+79109876543", position_id=pos3.id, created_by="Иванов И.И.")
        dir3 = Directors(name="Морозов Игорь Сергеевич", email="morozov@dir.ru", phone="+79105551122", position_id=pos1.id, created_by="Мария П.")
        dir4 = Directors(name="Лебедев Павел Александрович", email="lebedev@dir.ru", phone="+79103334455", position_id=pos4.id, created_by="Мария П.")
        session.add_all([dir1, dir2, dir3, dir4])
        await session.flush()

        # --- Organizations (Companies) ---
        org1 = Organization(name='ООО "ЭнергоПром"', inn="7701234567", address="г. Москва, ул. Ленина, д. 10", server_address_slug="/02_сторонние_заказчики", director_id=dir1.id, created_by="Иванов И.И.")
        org2 = Organization(name='АО "ТехноСтрой"', inn="7802345678", address="г. Санкт-Петербург, пр. Невский, д. 25", server_address_slug="/02_сторонние_заказчики", director_id=dir2.id, created_by="Иванов И.И.")
        org3 = Organization(name='ООО "УралЭнерго"', inn="6603456789", address="г. Екатеринбург, ул. Мира, д. 5", server_address_slug="/01_основные_заказчики", director_id=dir3.id, created_by="Мария П.")
        org4 = Organization(name='ПАО "СибЭлектро"', inn="5404567890", address="г. Новосибирск, ул. Красная, д. 100", server_address_slug="/02_сторонние_заказчики", director_id=dir4.id, created_by="Мария П.")
        session.add_all([org1, org2, org3, org4])
        await session.flush()

        # --- Counterparties ---
        cp1 = Counterparty(name="Захаров Павел Андреевич", email="zakharov@cp.ru", phone="+79201112233", company_id=org1.id, created_by="Иванов И.И.")
        cp2 = Counterparty(name="Белова Анна Игоревна", email="belova@cp.ru", phone="+79204445566", company_id=org2.id, created_by="Иванов И.И.")
        cp3 = Counterparty(name="Орлов Сергей Викторович", email="orlov@cp.ru", phone="+79207778899", company_id=org3.id, created_by="Мария П.")
        cp4 = Counterparty(name="Кузнецова Татьяна Олеговна", email="kuznetsova@cp.ru", phone="+79202223344", company_id=org4.id, created_by="Мария П.")
        cp5 = Counterparty(name="Федоров Максим Денисович", email="fedorov@cp.ru", phone="+79205556677", company_id=org1.id, created_by="Иванов И.И.")
        session.add_all([cp1, cp2, cp3, cp4, cp5])
        await session.flush()

        # --- Requests ---
        req1 = Request(
            counterparty_id=cp1.id, company_id=org1.id, manager_id=user1.id,
            status=RequestStatus.ZAPROS, description="Запрос на поставку КТПБ-1000",
            notes="Срочный заказ", created_by="Иванов И.И.",
            bktpb=2, ktpb=5, ktp=3, kso_393=1, kso_204=0,
            k_104=0, k_104m=0, sho=1, pku=0, pus=0, parn=0,
        )
        req2 = Request(
            counterparty_id=cp2.id, company_id=org2.id, manager_id=user2.id,
            status=RequestStatus.TENDER, description="Тендер на электромонтажные работы",
            notes="Тендер до 25.09", created_by="Иванов И.И.",
            bktpb=0, ktpb=2, ktp=1, kso_393=0, kso_204=3,
            k_104=2, k_104m=1, sho=0, pku=1, pus=0, parn=0,
        )
        req3 = Request(
            counterparty_id=cp3.id, company_id=org3.id, manager_id=user3.id,
            status=RequestStatus.DOC_PROCESSING, description="Оформление договора на КСО-393",
            notes="", created_by="Мария П.",
            bktpb=1, ktpb=0, ktp=0, kso_393=4, kso_204=0,
            k_104=0, k_104m=0, sho=2, pku=0, pus=1, parn=0,
        )
        req4 = Request(
            counterparty_id=cp4.id, company_id=org4.id, manager_id=user1.id,
            status=RequestStatus.ORDER, description="Заказ на поставку ЩО-12",
            notes="Доставка до конца месяца", created_by="Мария П.",
            bktpb=0, ktpb=1, ktp=2, kso_393=0, kso_204=1,
            k_104=0, k_104m=0, sho=5, pku=2, pus=0, parn=1,
        )
        req5 = Request(
            counterparty_id=cp5.id, company_id=org1.id, manager_id=user1.id,
            status=RequestStatus.WAITING_PAYMENT, description="Ожидание оплаты за ПКУ-10",
            notes="Счёт выставлен 01.08", created_by="Иванов И.И.",
            bktpb=0, ktpb=0, ktp=0, kso_393=0, kso_204=0,
            k_104=1, k_104m=0, sho=0, pku=3, pus=0, parn=0,
        )
        req6 = Request(
            counterparty_id=cp1.id, company_id=org1.id, manager_id=user1.id,
            status=RequestStatus.NOT_ACTUAL, description="Не актуально — клиент отказался",
            notes="", created_by="Иванов И.И.",
            bktpb=0, ktpb=0, ktp=0, kso_393=0, kso_204=0,
            k_104=0, k_104m=0, sho=0, pku=0, pus=0, parn=0,
        )
        session.add_all([req1, req2, req3, req4, req5, req6])
        await session.flush()

        # Generate tkp_num
        for req in [req1, req2, req3, req4, req5, req6]:
            u = await session.get(User, req.manager_id)
            req.tkp_num = f"{req.id}-{u.city}"

        await session.commit()
        print("Seed complete: 3 users, 4 positions, 4 directors, 4 companies, 5 counterparties, 6 requests")


asyncio.run(seed())
