export default function ErrorBox({ message }) {
  return message ? <div className="alert error">{message}</div> : null;
}
