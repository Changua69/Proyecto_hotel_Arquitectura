import API from "./api"

export const createReservation = (data: { room_number: number; guest_email: string; check_in: string; check_out: string }) => {
  return API.post("/reservations/create", data)
}