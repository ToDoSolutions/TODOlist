// Campo de fecha canónico: DatePicker MUI (x-date-pickers + date-fns).
// Usar en vez de <TextField type="date"> — picker consistente en todos
// los navegadores, con locale es-ES y formato dd/MM/yyyy.
// value/onChange usan el formato ISO "yyyy-MM-dd" que espera la API.
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { parseISO, format, isValid } from "date-fns";

interface DateFieldProps {
  label: string;
  value: string | undefined | null; // ISO yyyy-MM-dd o ""
  onChange: (value: string) => void;
  required?: boolean;
}

export function DateField({ label, value, onChange, required }: DateFieldProps) {
  const parsed = value ? parseISO(value) : null;
  return (
    <DatePicker
      label={label}
      value={parsed && isValid(parsed) ? parsed : null}
      onChange={(d) => onChange(d && isValid(d) ? format(d, "yyyy-MM-dd") : "")}
      format="dd/MM/yyyy"
      slotProps={{
        textField: {
          size: "small",
          fullWidth: true,
          required,
          slotProps: { inputLabel: { shrink: true } },
        },
      }}
    />
  );
}
