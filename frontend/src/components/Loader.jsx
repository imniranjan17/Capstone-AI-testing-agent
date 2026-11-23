export default function Loader({ message = "Loading" }) {
  return (
    <div className="loader">
      <div className="ring" />
      <span>{message}</span>
      <span className="dots"><span /><span /><span /></span>
    </div>
  );
}
