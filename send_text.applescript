-- usage: osascript send_text.applescript <phone number> <message text>
on run argv
	set recipient to item 1 of argv
	set msg to item 2 of argv
	tell application "Messages"
		try
			set svc to 1st account whose service type = iMessage
			send msg to participant recipient of svc
			return "sent via iMessage"
		on error errA
			try
				set svc2 to 1st account whose service type = SMS
				send msg to participant recipient of svc2
				return "sent via SMS"
			on error errB
				return "FAILED: " & errA & " / " & errB
			end try
		end try
	end tell
end run
