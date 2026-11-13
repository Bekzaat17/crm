import type { ClientRecord } from "@/lib/types";
import { todayInput } from "@/lib/format";

export function ClientFields({ client }: { client?: ClientRecord }) {
  return (
    <>
      <label>
        ФИО клиента
        <input
          name="name"
          required
          maxLength={240}
          defaultValue={client?.name}
        />
      </label>
      <div className="form-grid">
        <label>
          Телефон
          <input
            name="phone"
            type="tel"
            maxLength={40}
            defaultValue={client?.phone}
          />
        </label>
        <label>
          Город
          <input name="city" maxLength={120} defaultValue={client?.city} />
        </label>
      </div>
      <label>
        Дата рождения
        <input
          name="date_of_birth"
          type="date"
          max={todayInput()}
          defaultValue={client?.date_of_birth}
        />
      </label>
      <label>
        Заметки
        <textarea
          name="notes"
          maxLength={5000}
          rows={3}
          defaultValue={client?.notes}
        />
      </label>
    </>
  );
}
