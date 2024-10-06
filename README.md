
# Auto Layers

A tool to switch layer automatically on QMK and VIAL-QMK keyboards in function of the active window.

If you are going to fork:\
It relays on https://github.com/apmorton/pyhidapi and https://github.com/Infinidat/infi.systray so check the documentation especially for pyhidapi that needs extra steps to work.
## Warning
I just started learning Python so read the code and be careful.\
I'm not responsible of anything that might happen to you, your hardware or your software using this program.


## Demo

coming soon


## Usage

1 look at the tray\
2 right click and select a device, the selected device has the application icon\
3 double click to pause or resume, the icon turns orange if paused\
4 grab starts a timer, after selecting it put the device on the layer you want and focus the        application to associate them, you have 4 seconds before it'll be saved. If you need more time to change layer on your device you can pause before starting the grab process so that you only need to click on the application window and wait. You should see the icon change to the grab icon for a couple of seconds for confirmation.\
5 remove is timed too, you just need to click it, focus on the application you want to remove and wait for the icon change of confirmation\
6 usage at the same time with VIAL causes bad thing so if the process is detected it stops temporarly, even if it's not the foreground window, the icon turns red. You can add more application to this behaviour editing the block_list in the config.ini file, you'll also find a block_if_active list there to block auto layers only if those application are the active window.
## Firmware modifications

You need to add some code,

for VIAL-QMK:

keymap.c
```c
#include <raw_hid.h>

bool any_key_down = false;
uint16_t held_key = 0;

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
  if (record->event.pressed) {
	if (!any_key_down) {
	  held_key = keycode;
	}
	any_key_down = true;
  } else {
	  if (keycode == held_key) {
	    any_key_down = false;
	    held_key = 0;
	  }
  }
  return true;
}

enum my_command_id {
	id_current_layer   = 0x40,
	id_layer_0         = 0x30,
	id_layer_1         = 0x31,
	id_layer_2         = 0x32,
	id_layer_3         = 0x33,
	id_layer_4         = 0x34,
	id_layer_5         = 0x35,
	id_layer_6         = 0x36,
	id_layer_7         = 0x37,
	id_layer_8         = 0x38,
	id_layer_9         = 0x39,
};

void raw_hid_receive_kb(uint8_t *data, uint8_t length) {
	uint8_t *command_id   = &(data[0]);
	switch (*command_id) {
		case id_current_layer: {
            uint8_t response[length];
			memset(response, 0, length);
			
			/* count number of digits */
			int c = 0; /* digit position */
			int n = get_highest_layer(layer_state);

			while (n != 0)
			{
				n /= 10;
				c++;
			}

			int numberArray[c];

			c = 0;    
			n = get_highest_layer(layer_state);

			/* extract each digit */
			while (n != 0)
			{
				numberArray[c] = n % 10;
				n /= 10;
				c++;
			}
			
			int i;
			size_t max = sizeof(numberArray)/sizeof(numberArray[0]);
			for (i = 0; i < max; i++) {
				response[i] = numberArray[i];
			}

			raw_hid_send(response, length);
            break;
        }
		case id_layer_0: {
            if (!any_key_down) {
				layer_move(0);
			}
            break;
        }
		case id_layer_1: {
            if (!any_key_down) {
				layer_move(1);
			}
            break;
        }
		case id_layer_2: {
            if (!any_key_down) {
				layer_move(2);
			}
            break;
        }
		case id_layer_3: {
            if (!any_key_down) {
				layer_move(3);
			}
            break;
        }
		case id_layer_4: {
            if (!any_key_down) {
				layer_move(4);
			}
            break;
        }
		case id_layer_5: {
            if (!any_key_down) {
				layer_move(5);
			}
            break;
        }
		case id_layer_6: {
			if (!any_key_down) {
				layer_move(6);
			}
            break;
        }
		case id_layer_7: {
            if (!any_key_down) {
				layer_move(7);
			}
            break;
        }
		case id_layer_8: {
            if (!any_key_down) {
				layer_move(8);
			}
            break;
        }
		case id_layer_9: {
            if (!any_key_down) {
				layer_move(9);
			}
            break;
        }
	}
}
```

[sample keymap](https://github.com/itsvar8/vial-qmk/blob/cstc40/keyboards/kprepublic/cstc40/single_pcb/keymaps/vial/keymap.c)

for QMK:

keymap.c
```c
#include <raw_hid.h>

bool any_key_down = false;
uint16_t held_key = 0;

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
  if (record->event.pressed) {
	if (!any_key_down) {
	  held_key = keycode;
	}
	any_key_down = true;
  } else {
	  if (keycode == held_key) {
	    any_key_down = false;
	    held_key = 0;
	  }
  }
  return true;
}

enum my_command_id {
	id_current_layer   = 0x40,
	id_layer_0         = 0x30,
	id_layer_1         = 0x31,
	id_layer_2         = 0x32,
	id_layer_3         = 0x33,
	id_layer_4         = 0x34,
	id_layer_5         = 0x35,
	id_layer_6         = 0x36,
	id_layer_7         = 0x37,
	id_layer_8         = 0x38,
	id_layer_9         = 0x39,
};

void raw_hid_receive(uint8_t *data, uint8_t length) {
	uint8_t *command_id   = &(data[0]);
	switch (*command_id) {
		case id_current_layer: {
            uint8_t response[length];
			memset(response, 0, length);
			
			/* count number of digits */
			int c = 0; /* digit position */
			int n = get_highest_layer(layer_state);

			while (n != 0)
			{
				n /= 10;
				c++;
			}

			int numberArray[c];

			c = 0;    
			n = get_highest_layer(layer_state);

			/* extract each digit */
			while (n != 0)
			{
				numberArray[c] = n % 10;
				n /= 10;
				c++;
			}
			
			int i;
			size_t max = sizeof(numberArray)/sizeof(numberArray[0]);
			for (i = 0; i < max; i++) {
				response[i] = numberArray[i];
			}

			raw_hid_send(response, length);
            break;
        }
		case id_layer_0: {
            if (!any_key_down) {
				layer_move(0);
			}
            break;
        }
		case id_layer_1: {
            if (!any_key_down) {
				layer_move(1);
			}
            break;
        }
		case id_layer_2: {
            if (!any_key_down) {
				layer_move(2);
			}
            break;
        }
		case id_layer_3: {
            if (!any_key_down) {
				layer_move(3);
			}
            break;
        }
		case id_layer_4: {
            if (!any_key_down) {
				layer_move(4);
			}
            break;
        }
		case id_layer_5: {
            if (!any_key_down) {
				layer_move(5);
			}
            break;
        }
		case id_layer_6: {
			if (!any_key_down) {
				layer_move(6);
			}
            break;
        }
		case id_layer_7: {
            if (!any_key_down) {
				layer_move(7);
			}
            break;
        }
		case id_layer_8: {
            if (!any_key_down) {
				layer_move(8);
			}
            break;
        }
		case id_layer_9: {
            if (!any_key_down) {
				layer_move(9);
			}
            break;
        }
	}
}
```
[sample keymap](https://github.com/itsvar8/qmk_firmware/blob/cstc40/keyboards/kprepublic/cstc40/keymaps/default/keymap.c)

rules.mk
```mk
RAW_ENABLE = yes
```
[sample rules.mk](https://github.com/itsvar8/qmk_firmware/blob/cstc40/keyboards/kprepublic/cstc40/keymaps/default/rules.mk)
## If you found it useful...
...consider [donating](https://www.paypal.com/paypalme/itsvar8) so i can work more on things we both love, thanks!