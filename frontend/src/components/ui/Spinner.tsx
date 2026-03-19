export default function Spinner({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="w-6 h-6 border-2 border-[#1E2A3A] border-t-[#D4915E] rounded-full animate-spin" />
    </div>
  );
}
