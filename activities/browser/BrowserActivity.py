import logging
import xml.sax.saxutils

import gtk
import geckoembed

from sugar.activity.Activity import Activity
from sugar.presence.PresenceService import PresenceService
from sugar.p2p.model.LocalModel import LocalModel
from sugar.p2p.model.RemoteModel import RemoteModel

from NotificationBar import NotificationBar
from NavigationToolbar import NavigationToolbar

_SERVICE_URI_TAG = "URI"
_SERVICE_TITLE_TAG = "Title"

class BrowserActivity(Activity):
	SOLO = 1
	FOLLOWING = 2
	LEADING = 3

	def __init__(self, service, args):
		Activity.__init__(self, service)

		if len(args) > 0:
			self.uri = args[0]
		else:
			self.uri = 'http://www.google.com'
		
		self._mode = BrowserActivity.SOLO
		self._share_service = None
		self._model_service = None
		self._notif_service = None
		self._model = None

		self.set_title("Web Page")

		vbox = gtk.VBox()

		self._notif_bar = NotificationBar()
		vbox.pack_start(self._notif_bar, False)
		self._notif_bar.connect('action', self.__notif_bar_action_cb)

		self.embed = geckoembed.Embed()
		self.embed.connect("title", self.__title_cb)
		vbox.pack_start(self.embed)
		
		self.embed.show()
		self.embed.load_address(self.uri)
		
		nav_toolbar = NavigationToolbar(self)
		vbox.pack_start(nav_toolbar, False)
		nav_toolbar.show()

		self.add(vbox)
		vbox.show()

		self._pservice = PresenceService()
		self._pservice.connect('service-appeared', self._service_appeared_cb)

		# Join the shared activity if we were started from one
		if self._initial_service:
			logging.debug("BrowserActivity joining shared activity %s" %
						  self._initial_service.get_activity_id())
			self._pservice.join_shared_activity(self._initial_service)
	
	def _service_appeared_cb(self, pservice, service):
		# Make sure the service is for our activity
		if service.get_activity_id() != self._activity_id:
			return

		if service.get_type() == self._default_type:
			self._notif_service = service
		elif service.get_type() == LocalModel.SERVICE_TYPE:
			if self._mode != BrowserActivity.LEADING:
				self._model_service = service
		
		if not self._model and self._notif_service and self._model_service:
			self._model = RemoteModel(self._model_service, self._notif_service)
			self._model.add_listener(self.__shared_location_changed_cb)
	
	def _update_shared_location(self):
		address = self.embed.get_address()
		self._model.set_value('address', address)
		title = self.embed.get_title()
		self._model.set_value('title', title)
		
	def __notif_bar_action_cb(self, bar, action_id):
		if action_id == 'set_shared_location':
			self._update_shared_location()
		elif action_id == 'goto_shared_location':
			address = self._model.get_value("address")
			self.embed.load_address(address)
			self._notif_bar.hide()

	def set_mode(self, mode):
		self._mode = mode
		if mode == BrowserActivity.LEADING:
			self._notif_bar.set_text('Share this page with the group.')
			self._notif_bar.set_action('set_shared_location', 'Share')
			self._notif_bar.set_icon('stock_shared-by-me')
			self._notif_bar.show()

	def get_embed(self):
		return self.embed
	
	def share(self):
		escaped_title = xml.sax.saxutils.escape(self.embed.get_title())
		escaped_url = xml.sax.saxutils.escape(self.embed.get_address())

		# Share this activity with others
		properties = {_SERVICE_URI_TAG: escaped_url, _SERVICE_TITLE_TAG: escaped_title}
		self._share_service = self._pservice.share_activity(self,
				stype=self._default_type, properties=properties)

		# Create our activity-specific browser sharing service
		self._model = LocalModel(self, self._pservice, self._share_service)
		self._model.set_value('owner', self._pservice.get_owner().get_name())
		self._update_shared_location()
		
		self.set_mode(BrowserActivity.LEADING)

	def __title_cb(self, embed):
		self.set_title(embed.get_title())

	def __shared_location_changed_cb(self, model, key):
		self.set_has_changes(True)
		self._notify_shared_location_change()

	def _notify_shared_location_change(self):
		owner = self._model.get_value('owner')
		title = self._model.get_value('title')
		
		text = '<b>' + owner + '</b> is reading <i>' + title + '</i>'
		self._notif_bar.set_text(text)
		self._notif_bar.set_action('goto_shared_location', 'Go There')
		self._notif_bar.set_icon('stock_right')
		self._notif_bar.show()
